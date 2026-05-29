---
Task: t832_5_parallel_cross_repo_planning_procedure.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_6_retrospective_dogfooding_evaluation.md, aitasks/t832/t832_8_ait_board_cross_repo_support.md, aitasks/t832/t832_9_manual_verification_cross_repo.md
Archived Sibling Plans: aiplans/archived/p832/p832_1_cross_repo_retrieval_reexec_trio.md, aiplans/archived/p832/p832_2_explain_context_cross_repo.md, aiplans/archived/p832/p832_3_xdeps_parser_and_validation.md, aiplans/archived/p832/p832_4_xdeps_blocking_logic.md, aiplans/archived/p832/p832_7_cross_repo_task_update.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-28 12:00
---

# Plan: parallel cross-repo planning procedure (t832_5, revised)

## Context

After the cross-repo plumbing landed (t832_1 retrieval, t832_3 `xdeps` /
`xdeprepo` parser & validation, t832_7 cross-repo `aitask_update.sh
--project`), no planning surface yet knows how to **design a single
coordinated change spanning two aitasks projects**.

User direction (revised): the cross-planning procedure is invoked
during the **task-workflow planning phase** (the path reached via
`/aitask-pick`). The procedure **always splits the task into ≥2
children** — one per repo, usually more (because cross-repo work
naturally evolves in parallel stages). It creates the **cross-repo
parent first**, then walks the planned children one-by-one, attaching
each to whichever parent (local or cross-repo) is correct and wiring
deps via `depends:` (in-repo) and `xdeps:` / `xdeprepo:` (cross-repo).

## Scope restriction

t832_5 covers **aitask-pick only** (the planning phase inside
`task-workflow`). Two follow-up tasks are created:

1. `t832/t832_10_aitask_create_interactive_cross_repo.md` — sibling
   task that adds cross-repo support to `aitask-create` interactive
   mode (cross-repo question, file refs / task refs / labels with
   cross-repo references, `xdeprepo` stored in task metadata at
   creation time). Created at the start of this task's
   implementation phase (not part of the planning deliverable).
2. `t832/t832_11_aitask_explore_cross_repo.md` — sibling task for
   `aitask-explore` cross-repo integration; opened after the
   `aitask-create` sibling stabilises. Filed as a follow-up after
   t832_5 + t832_10 land.

## Verified deviations from the prior plan

- **Wire-in surface narrowed to one site:**
  `.claude/skills/task-workflow/planning.md` (Complexity Assessment
  branch). Previous draft also wired into `aitask-explore/SKILL.md.j2`
  — pulled out and deferred to t832_11. `aitask-create/SKILL.md` is
  not Jinja-templated and has no planning step — out of scope here.
- **Procedure shape:** previous design said "two parents whose
  children straddle repos is forbidden". Revised design **enforces**
  exactly that shape (two parents, mixed children) by always
  splitting and assigning children to whichever parent fits. The
  abort path stays as a safety net for malformed inputs.
- **Creation order:** previous design suggested reserving cross-repo
  child IDs first to back-fill `xdeps:`. Revised design creates the
  **cross-repo parent first** (so its ID is known), then iterates
  child-by-child — each child is created at the correct parent with
  fully-resolved deps at write time (no two-phase back-fill needed
  for the common case; back-fill via `aitask_update.sh --project` is
  only used when a later child's existence completes a forward
  reference from an earlier one).

## Key files to modify

| File | Change |
|------|--------|
| `.claude/skills/task-workflow/parallel-cross-repo-planning.md` | **NEW** procedure file (trigger detection + confirmation + paired exploration + decomposition + cross-repo-parent-first creation + commit-ordering + return contract). |
| `.claude/skills/task-workflow/planning.md` | Insert one-line dispatch at top of the Complexity Assessment branch (§6.1, ~line 187). |
| `aitasks/t832/t832_10_aitask_create_interactive_cross_repo.md` | **NEW** sibling task (created via `aitask_create.sh --parent 832 --batch`). |
| `tests/test_parallel_cross_repo_planning_procedure.sh` | **NEW** — exercises trigger detection, cross-repo-parent-first creation, deps wiring, push-failure warning. |

No Jinja `.md.j2` files are touched, so no goldens regen is needed for
this task. `task-workflow/planning.md` contains Jinja conditionals (no
`.j2` suffix), so `aitask_skill_verify.sh` still re-renders it via the
existing path — verify clean.

## Procedure content (`parallel-cross-repo-planning.md`)

Sections, in order:

### Step 0 — Trigger detection (metadata-only)

Caller passes `current_task_id`. The procedure inspects the task
frontmatter:

- Read `xdeprepo` via `./.aitask-scripts/aitask_query_files.sh
  task-file <id>` + frontmatter read (or directly via
  `lib/task_utils.sh::read_xdeprepo`).
- **Trigger fires iff `xdeprepo` is non-empty.** Extract `<name>` =
  `xdeprepo` value.
- No body-text scanning, no project-name matching, no notation regex
  — these are intentionally excluded to avoid false positives from
  incidental mentions.

If `xdeprepo` is empty / absent: set `cross_repo_handled: false` and
return immediately. The local-only flow continues.

**Note:** This means the trigger never fires until at least one of
the following is true for the picked task:
- The task was created via `aitask_create.sh --batch --xdeprepo
  <name> --xdeps ...` (already supported since t832_3).
- The task was created via `aitask-create` interactive in cross-repo
  mode (lands in sibling t832_10).
- The user manually added `xdeprepo:` to the frontmatter (via `ait
  board` edit, direct file edit, etc.).

The user-confirmation step (Step 0b) still fires so the planning
agent isn't dispatched without an explicit "yes" — `xdeprepo` records
intent at creation but the planning agent confirms before acting.

### Step 0b — Confirmation

`AskUserQuestion`:
- "Task frontmatter declares `xdeprepo: <name>`. Plan as a paired
  cross-repo task? The procedure will split into ≥2 children
  spanning both repos and create a counterpart parent in `<name>`."
- Options: "Yes, plan paired (Recommended)" / "No, plan locally only".

On "No": `cross_repo_handled: false`, return (the local-only flow
continues; `xdeprepo` stays in metadata for future picks).

`xdeprepo` is a scalar — exactly one cross-repo project per task —
so no disambiguation prompt is needed.

### Step 1 — Resolve both repos

Run `aitask_project_resolve.sh` for the matched cross-repo name. The
local project is implicit (current working directory). Die-with-hint
on STALE / NOT_FOUND.

### Step 2 — Paired exploration

Spawn two `Explore` subagents in parallel — one rooted in each repo —
with a focused question distilled from `trigger_source` (the
implementing agent composes the question). Subagent results stay in
this conversation's context for the decomposition step.

**Cross-repo reference resolution (added by t832_10 follow-up).** Before
spawning the subagents, scan `trigger_source` for the two notations
introduced by t832_10's interactive `aitask_create.sh` flow and
documented in `aidocs/cross_repo_references.md`:

- `<project>#<id>` (e.g. `aitasks_mobile#42_3`) — resolve to the
  referenced task's title/description via
  `aitask_query_files.sh --project <project> task-file <id>` and
  inline the resolved title into the question composed for the
  cross-repo subagent so it can reference the work by name.
- `<project>:<relative/path>` (e.g. `aitasks_mobile:Sources/Login.kt`)
  — resolve the cross-repo root via `aitask_project_resolve.sh
  <project>` → `RESOLVED:<root>`, then include the file at
  `<root>/<relative/path>` in the cross-repo subagent's reading
  list as a high-priority context file.

Both notations are authoring-only inside `trigger_source` — the
trigger itself remains `xdeprepo` metadata-only (per the architectural
decision in Step 0). These notations are resolved here, during
exploration, not during trigger detection.

### Step 3 — Design child decomposition (≥2 children)

Synthesise the cross-repo task as a sequence of **at least two**
children, typically more, because cross-repo work usually evolves in
parallel staged steps (e.g., add field on repo B → consume field on
repo A → migrate older payloads on repo B → display on repo A).

For each planned child, record:
- Owning repo (`local` or `<name>`).
- Title / brief description / labels / issue_type.
- In-repo deps (other planned children with same owning repo).
- Cross-repo deps (planned children on the opposite side that must
  finish first).

### Step 4 — Create cross-repo parent first

```bash
./.aitask-scripts/aitask_create.sh --project <name> --batch \
  --name "<mirrored title>" --priority <p> --effort <e> \
  --issue-type <t> --labels "<labels>" --commit \
  --description-file <tmp>
```

Capture `TASK_CREATED:<id>:<path>` line → `<B_parent_id>`. Use the
local task as the basis for `<mirrored title>` — usually `"<local
title> (cross-repo counterpart)"` unless the user supplied an
explicit override during Step 0b.

### Step 5 — Write children one-by-one

The local parent is `<current_task_id>` (the task driving
`/aitask-pick`). Iterate the planned children in dependency order
(topological sort; forward references inside the same side resolve
naturally, cross-repo forward references defer to Step 6 back-fill).

For each planned child:

- **If owning repo is local:**
  ```bash
  ./.aitask-scripts/aitask_create.sh --parent <current_task_id> --batch \
    --name "<child_name>" --priority <p> --effort <e> \
    --issue-type <t> --labels "<labels>" \
    --deps "<resolved_local_sibling_ids>" \
    --xdeps "<resolved_cross_repo_sibling_ids>" \
    --xdeprepo "<name>" \
    --description-file <tmp>
  ```
  When `--xdeps` is empty, omit both `--xdeps` and `--xdeprepo` (the
  validator enforces both-or-neither).

- **If owning repo is cross-repo:**
  ```bash
  ./.aitask-scripts/aitask_create.sh --project <name> --parent <B_parent_id> --batch \
    --name "<child_name>" --priority <p> --effort <e> \
    --issue-type <t> --labels "<labels>" \
    --deps "<resolved_cross_repo_sibling_ids>" \
    --xdeps "<resolved_local_sibling_ids>" \
    --xdeprepo "<local_project_name>" \
    --description-file <tmp>
  ```

For each child, capture the returned `TASK_CREATED:<id>:<path>` so
subsequent children that depend on it can reference the resolved ID
when they are written.

Also write each child's plan file to its parent's plan tree
(`aiplans/p<parent>/p<parent>_<N>_<name>.md` locally;
`aiplans/p<B_parent_id>/...` via the cross-repo project's own
`./ait git`). Per `aitask-pick`'s planning §6.1, the local plan
commits happen via `./ait git add aiplans/p<parent>/` + commit. The
cross-repo plan files are written/committed via the cross-repo
project's own `./ait git` (rooted in `<B-root>`).

### Step 6 — Forward-reference back-fill (rare)

If a topologically earlier child needed an `xdeps` reference to a
later-created child (cycle-breaking sequencing where strict ordering
isn't possible), back-fill via:

```bash
./.aitask-scripts/aitask_update.sh --project <name> --batch <B_child_id> \
  --xdeps "<resolved_ids>" --xdeprepo <local_project_name>
```

In practice this is uncommon — the topological sort plus the
"cross-repo parent first" rule usually avoids it. The procedure
should detect when it's needed and run the back-fill silently;
unreachable cycles abort with a clear error.

### Step 7 — Commit-ordering protocol

- Local task / child / plan commits use `./ait git` (delegates to
  separate aitask-data branch in non-legacy mode).
- Cross-repo commits and pushes happen inside the cross-repo project's
  own `./ait git` (driven by `aitask_create.sh --project ... --commit`
  and `aitask_update.sh --project ... --commit`).
- **Push-failure handling:** if any cross-repo `--commit` succeeds
  locally but its internal `./ait git push` fails, surface a clear
  warning:
  `WARN: cross-repo commits landed in <B-root> but push failed — run \`cd <B-root> && ./ait git push\` to publish.`
  Do **not** retry silently.

### Step 8 — Driver symmetry

The procedure produces the same paired output regardless of which
repo drives. This is enforced structurally: trigger detection, parent
creation, and child iteration are written in repo-agnostic terms; the
"cross-repo parent first" rule applies regardless of which side
called.

### Step 9 — Return contract

On success:
- `cross_repo_handled: true`
- `cross_repo_name: <name>`
- `cross_repo_parent_id: <B_parent_id>`
- `cross_repo_parent_path: <path-in-B>`
- `local_children: [(id, path), ...]`
- `cross_repo_children: [(id, path), ...]`

The caller (planning.md) MUST treat this as a terminal state for
§6.1's Complexity Assessment: skip its own child-creation /
child-plan-writing / child-task-checkpoint, jump straight to "Save
Plan to External File" for the local parent, then to the Checkpoint
("Approve and stop here" / "Start first child" / "Revise"). The
saved plan file for the local parent records the paired plan as
authoritative for both repos.

On user-cancel or aborted detection: `cross_repo_handled: false` +
reason — caller continues with local-only flow.

### Step 10 — Multi-agent porting follow-up note

After t832_5 lands (Claude Code), file three follow-up aitasks (each
top-level, not children of t832) to port `parallel-cross-repo-
planning.md` to Codex CLI, Gemini CLI (or `agy` if t812 redirects by
then), and OpenCode.

## Wire-in edit

**`task-workflow/planning.md` — top of Complexity Assessment branch
(§6.1, ~line 187, just before `- **Complexity Assessment:**`):**

```markdown
- **Cross-repo dispatch check (auto-fire with confirmation):** Read
  and follow `.claude/skills/task-workflow/parallel-cross-repo-
  planning.md` with `trigger_source` = the task body plus any
  `current_task_id` = the current task ID. Trigger detection is
  metadata-only (reads `xdeprepo` from the task frontmatter); body
  text is not scanned. If the procedure returns
  `cross_repo_handled: true`, paired parent + children have already
  been created in both repos — skip the rest of §6.1's Complexity
  Assessment / child-task batch creation / child-plan writing /
  manual-verification sibling / child-task checkpoint, and proceed
  to "Save Plan to External File" for the local parent. If
  `cross_repo_handled: false`, continue with Complexity Assessment
  below.
```

## Tests

`tests/test_parallel_cross_repo_planning_procedure.sh` — uses
`tests/lib/test_scaffold.sh::setup_fake_aitask_repo` twice to build
two synthetic projects, plus a temporary `projects.yaml`:

1. **Trigger via metadata:** task with `xdeprepo: <B>` in frontmatter
   → procedure dispatches.
2. **No trigger — empty `xdeprepo`:** task with `xdeprepo:` empty or
   absent → returns `cross_repo_handled: false` immediately; no
   cross-repo helpers invoked. Verify that incidental mentions of a
   registered project name or `aitasks#N_M` notation in the body
   alone do NOT trip the trigger.
3. **User declines confirmation:** `xdeprepo` set but Step 0b answer
   is "No, plan locally only" → returns `cross_repo_handled: false`;
   no cross-repo helpers invoked; `xdeprepo` metadata is left intact.
4. **Cross-repo parent created first:** assert that the cross-repo
   `aitask_create.sh --project <B> --batch` call lands **before** any
   local child creation, and that the captured `<B_parent_id>` is
   used as `--xdeprepo` target / `--parent` value for subsequent
   children.
5. **Children split across repos:** synthesise a 4-child plan (2
   local, 2 cross-repo) and assert each child is created with the
   correct parent and correct `xdeps:` / `xdeprepo:` fields.
6. **Push-failure warning:** point repo B's remote at a `file://`
   path that doesn't exist; run the cross-repo `--commit`; assert
   the `WARN: cross-repo commits landed in <B-root> but push failed`
   message fires.
7. **Forward-reference back-fill:** craft a 2-child plan where the
   local child must reference a cross-repo child that doesn't exist
   yet at its creation moment, but the topological sort forces this
   order; assert the procedure invokes `aitask_update.sh --project
   <B> --batch` to back-fill `xdeps` after both children are
   written, and the final on-disk YAML carries the symmetric
   references.

In addition:

- `./.aitask-scripts/aitask_skill_verify.sh` → PASS for all profiles
  after the `planning.md` edit.
- `shellcheck` clean on any helper shell touched (none expected —
  task is markdown + tests only).

## Verification

1. `bash tests/test_parallel_cross_repo_planning_procedure.sh` →
   all assertions pass.
2. `./.aitask-scripts/aitask_skill_verify.sh` → PASS for all
   profiles.
3. Manual smoke (recorded in Final Implementation Notes): invoke
   `/aitask-pick <some-task-with-cross-repo-reference>` against a
   synthetic prompt mentioning `aitasks_mobile#1_2`; verify the
   confirmation prompt fires, that declining produces the local
   single-task plan flow, and that accepting produces:
   - one cross-repo parent (mirrored title) created in
     `../aitasks_mobile`,
   - ≥2 children split across both repos with proper deps,
   - local plan file in `aiplans/p<parent>/`, cross-repo plan file
     in the cross-repo's `aiplans/`.
4. Regression: re-run `bash tests/test_xdeps_parser.sh`,
   `test_xdeps_validation.sh`, `test_xdeps_fold_warn.sh`,
   `test_query_files_cross_repo.sh`, and (if present)
   `test_update_project_flag.sh` — none should regress.

## Pre-implementation step — Create sibling task t832_10

Before authoring the procedure file, create the sibling task that
captures the `aitask-create` interactive cross-repo follow-up so
nothing is lost during this task's review cycle:

```bash
./.aitask-scripts/aitask_create.sh --parent 832 --batch \
  --name aitask_create_interactive_cross_repo \
  --priority medium --effort medium --issue-type feature \
  --labels "cross_repo,aitask_create" --commit \
  --description-file <(cat <<'EOF'
## Context

Sibling of t832_5. After the cross-planning procedure lands in
`task-workflow`, the `aitask-create` interactive flow itself needs
cross-repo awareness so cross-repo intent can be captured at create
time (rather than waiting for the planning phase).

## Scope

- Add a cross-repo question to `aitask-create` interactive Step 3
  ("Does this task involve a second repo?"). On Yes, pick from
  registered projects (resolved via `aitask_project_resolve.sh`).
- Store `xdeprepo` in the task frontmatter at creation.
- In cross-repo mode, all subsequent interactive UIs must support
  cross-repo references:
  - File references in description (file picker reads both repos).
  - Task references in deps and elsewhere (`xdeps` candidates pulled
    from cross-repo `aitask_query_files.sh --project`).
  - Labels (union of both repos' `labels.txt`).
- After creation, downstream `/aitask-pick` planning sees the
  `xdeprepo` metadata and trips the Match A signal in
  `parallel-cross-repo-planning.md` (already supported by t832_5).

## Out of scope

- aitask-explore cross-repo integration → t832_11.

See parent plan §t832 and the cross-planning procedure landed in
t832_5 for context.
EOF
)
```

(The actual sibling-task creation will use the canonical Batch Task
Creation Procedure — `task-creation-batch.md` — at implementation
time. The shell block above is illustrative of the metadata.)

## Out of scope

- Wire-in to `aitask-explore` (deferred to t832_11).
- Wire-in to `aitask-create` interactive (deferred to t832_10).
- Cross-repo merge coordination / transactional commits (t826
  scope).
- TUI surfacing of in-progress paired plans (t832_8 for `ait board`).
- Codex / Gemini / OpenCode ports of the new procedure (three
  separate top-level follow-up aitasks after this lands).
- Three-way (or N-way) cross-repo plans (single cross-repo project
  only).

## Step 9 reference

After implementation, the standard Step 9 (Post-Implementation) flow
applies: archive via `aitask_archive.sh 832_5`, push, and answer the
satisfaction-feedback prompt. The new procedure file and tests are
regular framework additions.

## Implementation order

1. Create sibling task t832_10 via `aitask_create.sh --parent 832
   --batch` (Pre-implementation step above).
2. Write `.claude/skills/task-workflow/parallel-cross-repo-planning.md`
   with the 10-step structure above.
3. Edit `task-workflow/planning.md` to add the one-line dispatch.
4. Write `tests/test_parallel_cross_repo_planning_procedure.sh`
   covering the eight scenarios above.
5. Run `./.aitask-scripts/aitask_skill_verify.sh` — confirm PASS.
6. Run the new test — confirm all assertions pass.
7. Manual smoke against a synthetic two-fake-projects scenario.
8. Append `plan_verified` entry to the plan file (already done in
   Step 6.1's verify-path append).
9. Step 8 review → commit → Step 9 archive.
