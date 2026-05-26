---
priority: medium
effort: high
depends: [t826_1]
issue_type: feature
status: Implementing
labels: [brainstorming, cross_repo, aitask_query, aitask_create]
children_to_implement: [t832_1, t832_2, t832_3, t832_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-25 22:30
updated_at: 2026-05-26 18:27
boardidx: 80
---

Brainstorm and scope: teach framework skills and helper scripts to use the
cross-repo plumbing landed in t826_1 (`~/.config/aitasks/projects.yaml`
registry + `aitask_project_resolve.sh` + `ait projects` + `aitask_create.sh
--project`). Today nothing under `.claude/skills/` consumes that surface;
the `aitasks#835_3` notation is documented in `aidocs/cross_repo_references.md`
but has no parser. Three concrete scopes converged on during the
`/aitask-explore` session that produced this task:

## Scope 1 — Cross-repo retrieval in `aitask_query_files.sh` and kin

Add `--project <name>` to the file/plan-lookup family so skills (and
`aitask_explain_context.sh`, `aitask-explain`, `aitask-revert`,
`aitask-fold`, etc.) can read tasks and plans — including archived ones —
from a sister registered project without hardcoding `../path/`.

Touchpoints to extend (additive `--project <name>` flag; resolver
re-execs the sibling's own script):

- `.aitask-scripts/aitask_query_files.sh` — all subcommands (`task-file`,
  `has-children`, `child-file`, `sibling-context`, `plan-file`,
  `archived-children`, `archived-task`, `active-children`, `resolve`,
  `recent-archived`). Archived-resolution path must work cross-repo.
- `.aitask-scripts/aitask_ls.sh` — `--project <name>` filter (read-only
  listing of the sister's task table).
- `.aitask-scripts/aitask_find_by_file.sh` — cross-repo lookup so the
  explain/codebrowser cache can attribute a file to a sister-project task.
- `.aitask-scripts/aitask_explain_context.sh` — accept
  `--project <name>:<file>` pairs (or `aitasks#path` notation) so a
  planning agent can gather context across both repos in one call.

Pattern: resolve `<name>` via `aitask_project_resolve.sh`, then re-exec
the sibling's helper inside that root (mirrors how
`aitask_create.sh --project` already works). Out-of-scope helpers like
`aitask_codeagent.sh`, `aitask_skillrun.sh` stay local.

## Scope 2 — Cross-repo dependencies (`xdepends` + `xdependrepo`)

New frontmatter fields, deliberately kept simple:

- `xdependrepo: <externalreponame>` — scalar; the sister project (must
  resolve via the registry).
- `xdepends: [N, N_M, ...]` — task numbers in the regular local format,
  interpreted **inside `xdependrepo`**.

Rationale (per user direction): scalar repo keeps parsing trivial — one
external repo per task, lists stay flat. Avoids per-entry tagging like
`aitasks#835_3`. Notation in `aidocs/cross_repo_references.md` remains
the human-authoring form (plans, commit messages); `xdepends` /
`xdependrepo` is the machine-readable form skills/scripts consume.

Touchpoints:

- `task_utils.sh` YAML parser — recognize both fields.
- `aitask_pick_own.sh` — extend blocking logic; a task with unmet
  `xdepends` is blocked until the sister tasks reach `Done`. Sister-side
  status is fetched via the Scope-1 cross-repo `aitask_query_files.sh`.
- `aitask_create.sh` / `aitask_fold_validate.sh` — validate the pair
  (both present or both absent; `xdependrepo` resolves; `xdepends`
  numbers exist sister-side).
- `aitask_board.py` / `ait monitor` — out of scope for v1 (display
  unchanged; cross-repo blocking is invisible in the UI). Surface in a
  follow-up if needed.

## Scope 3 — Parallel cross-repo planning procedure

A new shared procedure (working location:
`.claude/skills/task-workflow/parallel-cross-repo-planning.md`) wired
into the planning sites of `aitask-explore` / `aitask-create` (or
exposed as a dedicated skill, e.g. `aitask-cross-plan`).

Behavior:
1. Resolve both repos via the registry. Run codebase scans in **both**
   in parallel (likely via the Explore subagent, one per repo).
2. Design **paired** child-task decompositions: a single coordinated
   plan covering both repos, with the dependency graph spanning both.
3. Write **two separate parent tasks** — one per repo — each with its
   own children (regular `depends:` for in-repo edges, `xdepends:` +
   `xdependrepo:` for cross-repo edges).
4. Rule: never a single parent whose children straddle two repos. Each
   repo's hierarchy stays locally complete and valid; only the
   cross-repo edges are external.
5. The procedure must be runnable from either repo as the "driver";
   the same paired output is produced regardless of which side starts.

Open design questions to settle during the brainstorm:

- Where does the procedure live — shared module under `task-workflow`,
  or a dedicated `aitask-cross-plan` skill family with its own profile
  matrix? (Latter is heavier; former requires a profile-check gate.)
- Commit-ordering: the two parents land in two repos at different times
  — should the procedure stage both, present a single approval, then
  commit each? What if the sister's `./ait git` push fails halfway?
- Numbering coordination: child numbering inside each parent is local
  (Repo A: t100_1..t100_3; Repo B: t77_1..t77_3). `xdepends` references
  are by the sister's local number — the procedure must hand out IDs
  in lockstep so cross-edges resolve at write time.

## Out of scope (separate brainstorms if needed)

- Cross-project parent linkage (`--project X --parent Y` in
  `aitask_create.sh`) — explicitly excluded by t826_1 and **not
  re-introduced here**; the parallel-planning model is "two parents,
  one per repo", which sidesteps the need.
- Auto-clone of `NOT_FOUND` sister repos from `git_remote` — t826_5
  scope.
- TUI surfacing of cross-repo dependencies in `ait board` / `ait monitor` —
  follow-up after `xdepends` lands and gets dogfooded.
- Cross-repo *merge* coordination or transactional commits — carried
  over from parent brainstorm t826.

## Brainstorm goals

1. Lock the `--project <name>` re-exec contract for the
   `aitask_query_files` family (Scope 1) — error semantics for
   `NOT_FOUND` / `STALE`, exit-code conventions, archived-path
   resolution across registry entries.
2. Finalize `xdepends` / `xdependrepo` schema (scalar vs list debate
   already settled toward scalar — re-examine only if the parallel-
   planning procedure needs per-entry repo tagging).
3. Decide procedure home and skill surface for Scope 3 (shared
   procedure vs new skill family); spec the commit/numbering protocol.
4. Spawn child implementation tasks (probably one per scope, plus a
   shared `xdepends` parser task that both Scope 2 and Scope 3
   consume).

## References

- Foundation: `aiplans/archived/p826/p826_1_*` (registry + resolver +
  `ait projects` + `--project` flag).
- Authoring aidoc: `aidocs/cross_repo_references.md` — registry schema,
  resolver protocol, `aitasks#N` notation, current "what is NOT in
  scope" list (this task picks up several of those items).
- Sibling t826 children that stay independent: t826_2 (TUI switcher),
  t826_3 (website docs), t826_4 (manual verification), t826_5
  (stale-registry UX brainstorm).
- Origin pain example: `aitasks_mobile/aitasks/archived/t13/t13_2_sister_qr_add_hostname_field.md`
  — cross-repo task creation that today still has to hardcode `../`
  paths for everything except the create call itself.
