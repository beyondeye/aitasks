---
priority: medium
effort: high
depends: [t832_1, t832_3, t832_7]
issue_type: feature
status: Ready
labels: [cross_repo, task_workflow]
created_at: 2026-05-26 18:28
updated_at: 2026-05-28 12:05
---

## Context

Part of t832 brainstorm decomposition. Adds a new shared procedure that
makes it possible to plan a single coordinated change spanning two
aitasks projects (e.g., `aitasks` + `aitasks_mobile`) with a unified
dependency graph, while keeping each repo's task hierarchy locally
complete and valid.

**Architectural decision (user-confirmed):** Lives as a **shared module
under `task-workflow`**, NOT a new user-invocable skill. Called from
the planning sites of `aitask-explore` and `aitask-create`.

## Key Files to Modify

- **New procedure:** `.claude/skills/task-workflow/parallel-cross-repo-planning.md`
- **Wire-in sites:**
  - `.claude/skills/aitask-explore/SKILL.md.j2` planning site.
  - `.claude/skills/aitask-create/SKILL.md.j2` planning site.
- **Trigger:** the user's prompt mentions a registered cross-repo project
  name, OR the task body contains the `<name>#<id>` notation parsed via the
  `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$` regex from
  `aidocs/cross_repo_references.md`.

## Reference Files for Patterns

- `aidocs/cross_repo_references.md` — registry schema, resolver protocol,
  `aitasks#N` notation regex, current "what is NOT in scope" list.
- `.aitask-scripts/aitask_project_resolve.sh` — name → root resolution.
- `.aitask-scripts/aitask_query_files.sh --project <name>` (from t832_1) —
  cross-repo task lookup for numbering lockstep.
- `.aitask-scripts/aitask_create.sh --project <name>` (from t826_1) — create
  task in cross-repo project.
- `.aitask-scripts/aitask_update.sh --project <name>` (from t832_7) —
  update task in cross-repo project; required for symmetric cross-edges.
- `aiplans/p826/p826_1_*` (archived) — registry + resolver foundation.

## Procedure (5 steps to encode in the new shared module)

1. **Resolve both repos** via `aitask_project_resolve.sh` for each named
   project. Run codebase scans in **both** in parallel via the Explore
   subagent (one per repo) — each subagent gets the repo root and the
   focused question.
2. **Design paired child decompositions:** a single coordinated plan with
   the dependency graph spanning both repos.
3. **Two parents, never one** (load-bearing rule): write two separate parent
   tasks — one per repo — each with its own children. Use regular `depends:`
   for in-repo edges and `xdeps:` + `xdeprepo:` for cross-repo edges.
4. **Numbering lockstep:**
   - Reserve IDs in repo B via `aitask_create.sh --project B --batch ...`
     (capture the returned `TASK_CREATED:<id>:<path>` line if available, or
     parse the printed filename).
   - Write local children in repo A with the now-known B IDs in their
     `xdeps:`.
   - For symmetric cross-edges (B → A too), use `aitask_update.sh
     --project B --xdeps ...` (from t832_7) to back-fill.
5. **Driver symmetry:** the procedure produces identical output regardless
   of which repo is the driver.

## Commit-ordering protocol

- Local children land in the driver repo first (regular `./ait git commit`).
- Cross-repo children land via `aitask_create.sh --project <name> --batch
  ... --commit` (cross-repo project's own `./ait git` commits and pushes in
  its root).
- If the cross-repo `--commit` fails halfway (push error), surface a clear
  "cross-repo side committed but did not push — run `cd <cross-repo-root>
  && ./ait git push`" warning instead of retrying silently.

## Multi-agent porting

Per CLAUDE.md convention: implement Claude Code first under
`.claude/skills/task-workflow/`. Suggest separate follow-up aitasks to
port to:
- Codex CLI (`.agents/skills/task-workflow/`)
- Gemini CLI (`.gemini/skills/task-workflow/`)
- OpenCode (`.opencode/skills/task-workflow/`)

Do NOT bundle the ports here.

## Implementation Plan

1. Author `.claude/skills/task-workflow/parallel-cross-repo-planning.md`
   with the 5-step procedure above and the commit-ordering protocol.
2. Identify the planning sites in `aitask-explore/SKILL.md.j2` and
   `aitask-create/SKILL.md.j2` (likely near the EnterPlanMode invocation
   or the complexity-assessment branch).
3. Add a trigger check (regex parse + registry lookup); on match, read
   the new procedure file and execute its steps.
4. Re-render skills via `./.aitask-scripts/aitask_skill_render.sh` for
   each agent profile and verify with `./.aitask-scripts/aitask_skill_verify.sh`.
5. Regenerate goldens for the affected `.md.j2` outputs in the same
   commit (per `aidocs/skill_authoring_conventions.md`).

## Verification Steps

- `./.aitask-scripts/aitask_skill_verify.sh` passes for aitask-explore and aitask-create across all profiles.
- New test: `tests/test_parallel_cross_repo_planning_procedure.sh`
  - Two fake projects.
  - Dry-run procedure exercising the numbering lockstep (verify IDs are
    reserved cross-repo before local children are written).
  - Verify the "cross-repo committed but did not push" warning surfaces
    when the cross-repo `--commit` push fails (simulate via offline remote).
  - Verify the "two parents, never one" rule fires as a precondition error
    if the procedure is invoked with a single-parent-spanning-repos request.

## Notes for sibling tasks

- After this lands, suggest 3 follow-up aitasks for Codex/Gemini/OpenCode
  ports (see Multi-agent porting above).
- t832_6 will dogfood this procedure on a real `aitasks` + `aitasks_mobile`
  coordination task and document friction.

## Cross-repo reference resolution (added by t832_10 follow-up)

t832_10 introduced two notations into task descriptions written via
the interactive `aitask_create.sh` flow:

- `<project>#<id>` (e.g. `aitasks_mobile#42_3`) — a reference to a
  task in the cross-repo project.
- `<project>:<relative/path>` (e.g. `aitasks_mobile:Sources/Login.kt`)
  — a reference to a file in the cross-repo project root.

The procedure landed by this task **must resolve both notations** when
they appear in a task description that triggers paired planning:

- For `<project>#<id>` references: re-read the referenced task's
  title/description via
  `aitask_query_files.sh --project <project> task-file <id>` so the
  cross-planning prompt can quote the referenced task by name (not by
  bare ID).
- For `<project>:<relative/path>` references: resolve the cross-repo
  root via `aitask_project_resolve.sh <project>` → `RESOLVED:<root>`,
  then read the file at `<root>/<relative/path>` when exploring shared
  context during Step 2 (paired exploration).

The notations are documented in `aidocs/cross_repo_references.md`.
Both are authoring-only inside the trigger source — the trigger itself
remains `xdeprepo` metadata-only (per the architectural decision); the
notations are consumed during the planning exploration phase, not
during trigger detection.

## Out of scope

- The Codex/Gemini/OpenCode ports (separate follow-ups).
- Cross-repo merge coordination / transactional commits (parent t826 scope).
- TUI surfacing of in-progress paired plans (owned by t832_8 for board).

See parent plan §t832_5 for the full design context.
