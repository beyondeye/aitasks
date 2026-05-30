# Cross-Repo Child Assignment Procedure (creation)

Creates the cross-repo parent and assigns the children of a paired cross-repo
plan to their parents — local children under the current task, cross-repo
children under a newly created counterpart parent. It is the **creation**
half of cross-repo planning; the **design** half (read-only, runs during
planning) lives in `planning-cross-repo.md`.

**This procedure runs only after the paired plan is approved.** It is
dispatched from task-workflow **Step 7 (Implement)** when `cross_repo_planned`
is `true` (set by `planning-cross-repo.md` via `planning.md` §6.1). Creation
is deliberately deferred to here because planning runs in plan mode
(read-only) — no task may be created during Step 6. This mirrors the
single-repo decomposition flow, where children are created after the plan is
approved.

## Input context (from Step 7)

| Variable | Description |
|----------|-------------|
| `current_task_id` | The **local** parent (this task). |
| `cross_repo_name` | The cross-repo project `<name>` (from the approved plan / `xdeprepo`). |
| approved design | The paired decomposition recorded in the local parent's plan by `planning-cross-repo.md` Step 6 — the per-child `label / side / nominal parent / in-repo deps / cross-repo deps / description` table, plus the mirrored cross-repo parent title. |

## Return contract

Returns `cross_repo_executed: true`, `cross_repo_name`,
`cross_repo_parent_id`, `cross_repo_parent_path`, `local_children: [(id,
path), ...]`, `cross_repo_children: [(id, path), ...]`.

---

### Step 1 — Create the cross-repo parent first

Creating B's parent first means its ID is known before any child needs it as
an `--xdeprepo`/`--parent` target. Write the parent description (heredoc per
`task-creation-batch.md`) and run:

```bash
./.aitask-scripts/aitask_create.sh --project <name> --batch \
  --name "<mirrored_title>" --priority <p> --effort <e> \
  --type <t> --labels "<labels>" --commit --silent \
  --desc-file -
```

`--silent` prints **only** the created filepath on stdout (the commit message
goes to stderr). Capture that line and derive `<B_parent_id>` from the
basename: strip the leading `t`, the `.md` suffix, and the trailing `_<slug>`
(keep the numeric ID prefix; e.g. `t77_mirror_login.md` → `77`). Base
`<mirrored_title>` on the local task — typically `"<local title> (cross-repo
counterpart)"` unless the user supplied an override during the design's
confirmation step.

### Step 2 — Create and assign children one-by-one (local + cross-repo)

The **local** parent is `<current_task_id>`. Iterate the planned children in
dependency order (topological sort over the design's labels), resolving each
symbolic label dep to the real ID captured as creation proceeds. Write each
child's description (heredoc), then:

- **If owning side is local (assign under the local parent):**
  ```bash
  ./.aitask-scripts/aitask_create.sh --parent <current_task_id> --batch \
    --name "<child_name>" --priority <p> --effort <e> \
    --type <t> --labels "<labels>" \
    --deps "<resolved_local_sibling_ids>" \
    --xdeps "<resolved_cross_repo_sibling_ids>" --xdeprepo "<name>" \
    --commit --silent --desc-file -
  ```
  - For in-repo dependencies pass `--deps "<ids>"` directly (merged with the
    automatic prior-sibling dep). Omit `--deps` when there are none.
  - When there are no cross-repo deps, **omit both** `--xdeps` and
    `--xdeprepo` (the validator enforces both-or-neither).

- **If owning side is cross-repo (assign under the cross-repo parent):**
  ```bash
  ./.aitask-scripts/aitask_create.sh --project <name> --parent <B_parent_id> --batch \
    --name "<child_name>" --priority <p> --effort <e> \
    --type <t> --labels "<labels>" \
    --xdeps "<resolved_local_sibling_ids>" --xdeprepo "<local_project_name>" \
    --commit --silent --desc-file -
  ```
  Same both-or-neither rule for `--xdeps`/`--xdeprepo`.

Capture each created child's filepath, derive its ID from the basename, and
record the `label → id` mapping so later children resolve their deps. Also
write each child's **plan file**: `aiplans/p<parent>/p<parent>_<N>_<name>.md`
for local children (committed via `./ait git add aiplans/p<parent>/`);
`aiplans/p<B_parent_id>/...` for cross-repo children (written and committed via
the cross-repo project's own `./ait git`, rooted in `<B-root>`). Use the child
plan naming + metadata header conventions from `planning.md` (Save Plan to
External File).

### Step 3 — Forward-reference back-fill (rare)

If a topologically earlier child needed an `xdeps` reference to a
later-created child, back-fill after both exist:

```bash
./.aitask-scripts/aitask_update.sh --project <name> --batch <B_child_id> \
  --xdeps "<resolved_ids>" --xdeprepo <local_project_name>
```

The "cross-repo parent first" rule plus the topological sort usually avoid
this. Detect when it is needed and run the back-fill silently; abort with a
clear error on an unbreakable cycle.

### Step 4 — Demote the local parent to a parent-of-children

The local task is now a parent whose children carry the work — only the
children get implemented. Mirror the single-repo decomposition cleanup:

```bash
./.aitask-scripts/aitask_update.sh --batch <current_task_id> --status Ready --assigned-to ""
./.aitask-scripts/aitask_lock.sh --unlock <current_task_id> 2>/dev/null || true
```

`aitask_ls.sh` then shows it as "Has children". Do not set it to "Blocked".

### Step 5 — Commit-ordering protocol

- Local task / child / plan commits use `./ait git` (routes to the separate
  aitask-data branch in non-legacy mode).
- Cross-repo commits and pushes happen inside the cross-repo project's own
  `./ait git`, driven by `aitask_create.sh --project ... --commit` and
  `aitask_update.sh --project ... --commit`.
- **Push-failure handling:** if a cross-repo `--commit` lands locally but its
  internal `./ait git push` fails, surface a clear warning and do **not**
  retry silently:

  > `WARN: cross-repo commits landed in <B-root> but push failed — run \`cd <B-root> && ./ait git push\` to publish.`

### Step 6 — Driver symmetry

The procedure produces the same paired output regardless of which repo is the
driver. This is structural: parent creation and child iteration are
repo-agnostic, and the "cross-repo parent first" rule applies whichever side
called.

### Step 7 — Return contract and child checkpoint

Return the contract: `cross_repo_executed: true`, `cross_repo_name`,
`cross_repo_parent_id`, `cross_repo_parent_path`, `local_children`,
`cross_repo_children`.

Then present the cross-repo child checkpoint (mirrors the single-repo child
checkpoint) via `AskUserQuestion`:
- Question: "Created the cross-repo parent in `<name>` plus N children across
  both repos. How would you like to proceed?"
- Header: "Children"
- Options:
  - "Start first child" (description: "Continue to pick and implement the first child task")
  - "Stop here" (description: "All paired tasks + plans are written — pick children later in fresh contexts")
- **"Start first child":** restart with `/aitask-pick <current_task_id>_1`.
- **"Stop here":** collect the **Satisfaction Feedback Procedure** (see
  `satisfaction-feedback.md`) with `skill_name` from context, then END the
  workflow.

In both cases the workflow does **not** continue to the normal Step 8 code
review — the "work" was paired task creation, already committed in Steps 1-5.

### Step 8 — Follow-up notes

After this procedure lands (Claude Code first, per CLAUDE.md), file separate
follow-up aitasks to port both cross-repo procedures to the other supported
coding agents (Codex CLI, `agy`/Gemini, OpenCode) and to wire the same
dispatch into `aitask-explore`. Do not bundle those ports here.
