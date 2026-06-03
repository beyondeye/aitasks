---
Task: t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Base branch: main
plan_verified: []
---

# t832 — Cross-repo skills retrieval, xdeps, parallel planning (brainstorm → children)

## Context

`t826_1` landed the cross-repo plumbing foundation: per-user registry at
`~/.config/aitasks/projects.yaml`, the `aitask_project_resolve.sh`
resolver, the `ait projects` dispatcher, and `aitask_create.sh --project`.
Today **nothing else** in the framework consumes that surface — the
`aitasks#835_3` notation is documented in `aidocs/cross_repo_references.md`
but has no parser, no skill reads cross-repo tasks, and there's no
cross-repo dependency mechanism. Cross-repo coordination tasks (the
origin pain example: `aitasks_mobile/aitasks/archived/t13/t13_2_*`) still
hardcode `../path/` for every non-create operation.

**t832 is a brainstorming task.** Its deliverable is to lock the open
design decisions and spawn the implementation children. The user has
already settled three structural questions:

1. **Procedure home for parallel-planning (Scope 3):** Shared module under
   `.claude/skills/task-workflow/parallel-cross-repo-planning.md` (NOT a
   separate user-invocable skill).
2. **`xdeps` "satisfied" semantics:** `Done` only — mirrors the local
   `depends:` semantics exactly.
3. **Cross-repo resolver error policy:** Die with hint (matches
   `aitask_create.sh --project` at lines 1729-1752); do not invent a new
   structured-line convention.

Plan-agent validation surfaced two additional corrections embedded below:
`aitask_explain_context.sh` does not fit the uniform re-exec pattern (its
cache + Python-formatter aggregation require per-file pair dispatch), and
`aitask_ls.sh`'s cross-repo blocking-logic needs a cheap `task-status`
probe rather than re-exec'ing the full lister per dependency.

## Decomposition into 8 child tasks

Child IDs are numbers-only per CLAUDE.md convention. The dependency graph:

```
t832_1 ─┬─→ t832_2 (explain cross-repo)
        ├─→ t832_3 (xdeps parser + create/fold validation)
        │     ├─→ t832_4 (xdeps blocking logic)
        │     │     └─→ t832_8 (ait board TUI cross-repo support)
        │     └─→ t832_5 (parallel-planning procedure) ←─ t832_7 (cross-repo update)
        ├─→ t832_4, t832_5 (use task-status probe)
        └─→ t832_7 (re-exec pattern mirror)
                                    └─→ t832_6 (retrospective dogfooding)
```

Cross-repo *create* is already shipped (t826_1's `aitask_create.sh --project`).
t832_7 adds cross-repo *update*, completing the mutation surface needed for
t832_5's bidirectional cross-edge wiring (see t832_7 details below). No
cross-repo *archive* is proposed — archival is naturally bound to the
picking/implementing context of the owning repo (lock release + plan
archival + push), so reaching across to archive invites split-brain; the
existing `cd <cross-repo-root> && /aitask-pick` flow covers paired closure cleanly.

### t832_1 — Scope 1a: cross-repo retrieval (re-exec trio + status probe)

Add `--project <name>` to three helpers via a uniform argv-prefix transform
in `main()`, mirroring `aitask_create.sh:1693-1753`:

- `.aitask-scripts/aitask_query_files.sh` — wrap all subcommands (`task-file`,
  `has-children`, `child-file`, `active-children`, `all-children`,
  `sibling-context`, `plan-file`, `archived-children`, `archived-task`,
  `resolve`, `recent-archived`). Archived-resolution path automatically
  works cross-repo since re-exec runs the the cross-repo project's own helper in its root,
  which uses the cross-repo project's `ARCHIVED_DIR`.
- `.aitask-scripts/aitask_ls.sh` — read-only listing of the cross-repo
  project's task table with `--project <name>` filter.
- `.aitask-scripts/aitask_find_by_file.sh` — file-reference search across
  the cross-repo project so the explain/codebrowser cache can attribute a file
  to a cross-repo task.

**New subcommand:** `aitask_query_files.sh task-status <N|N_M>` returning
one line: `STATUS:Ready|Editing|Implementing|Postponed|Done|Folded|NOT_FOUND`.
This is required by t832_4's blocking logic — re-exec'ing the full
`aitask_ls.sh` per dependency edge is wrong granularity, and the
cross-repo side `read_task_status` from `task_utils.sh` is the natural source.

**Re-exec pattern (copy from `aitask_create.sh:1729-1752`):**
- Parse `--project <name>` out of argv before subcommand dispatch.
- `resolved=$(aitask_project_resolve.sh "$name")`; `case` on
  `RESOLVED:` / `STALE:` / `NOT_FOUND:`.
- On success: `cd "$root"; exec "$root/.aitask-scripts/<this-helper>.sh" "${forwarded[@]}"`.
- On failure: `die` with `cd /path/to/<name> && ait projects add` hint.

**Out-of-scope deferrals (do NOT extend in t832_1):** `aitask_revert_analyze.sh`
(future revert cross-attribution), `aitask_codeagent.sh`, `aitask_skillrun.sh`
(stay local). Skill files (`aitask-qa`, `aitask-pick`, etc.) themselves
do not need `--project` wiring — the helpers expose it, callers opt in.

**Tests:** `tests/test_query_files_cross_repo.sh` — synthesize two fake
aitasks roots in `tmp/`, register them via `AITASKS_PROJECTS_INDEX=...`,
exercise re-exec for each subcommand including the new `task-status`.

**depends:** `[]`

---

### t832_2 — Scope 1b: `aitask_explain_context.sh` cross-repo

**This does not fit the re-exec pattern.** The helper writes a cache under
`.aitask-explain/codebrowser/` (line 20) and calls a single Python
formatter (`aitask_explain_format_context.py` at line 251) that emits one
aggregated markdown blob. Re-exec'ing into the cross-repo project's root would (a)
write the cache in the cross-repo project's tree and (b) require the caller to merge
two markdown blobs by hand — defeating the purpose of "one call for
planning context".

**Correct shape:** accept `--project <name>:<file>` pairs (and the
human-authoring `aitasks#path` notation) at `parse_args()`. Group inputs
by `(project_name, dir_key)`. For each cross-repo project's group, dispatch
the extract pipeline (`aitask_explain_extract_raw_data.sh`) inside that
project's root (so the cache lands in the cross-repo project's tree where its
codebrowser already lives). Collect `ref:rundir` pairs from all projects.
Pass the merged `--ref` arg list to a **single** `aitask_explain_format_context.py`
call so the final markdown is a unified planning-context document.

**Key files:**
- `.aitask-scripts/aitask_explain_context.sh:48-71` (argument parsing).
- `.aitask-scripts/aitask_explain_context.sh:154-207` (`process_directory`
  — wrap to take a project root, default to local).
- `.aitask-scripts/aitask_explain_context.sh:209-255` (main — aggregation).
- Do NOT touch `aitask_explain_format_context.py` — it already accepts
  multiple `--ref` pairs.

**Tests:** end-to-end run with two fake projects, verify the single
markdown output contains plans from both.

**depends:** `[t832_1]` (uses `aitask_project_resolve.sh` directly, not
the re-exec pattern from t832_1; the dep is for the registry being
exercised + the conventions being settled).

---

### t832_3 — Scope 2 foundation: `xdeps` / `xdeprepo` parser + create/fold validation

**Schema (user-confirmed):**
- `xdeprepo: <name>` — scalar; the cross-repo project (must resolve via
  the registry).
- `xdeps: [N, N_M, ...]` — task numbers in the regular local format,
  interpreted **inside `xdeprepo`**.

**Parser changes:**
- `.aitask-scripts/aitask_ls.sh:222-225` (`parse_yaml_frontmatter` `case`)
  — add `xdeprepo)` and `xdeps)` arms storing into new variables.
  Reuse `parse_yaml_list` and `normalize_task_ids` from `task_utils.sh`
  (no changes needed there; they handle the proposed shapes).
- `lib/task_utils.sh` — add `read_xdeps`, `read_xdeprepo` thin
  wrappers around `read_yaml_field` + `parse_yaml_list`.

**TUI / Python parser audit (Plan-agent confirmed clean):**
`board/task_yaml.py:81` uses `yaml.safe_load` and round-trips unknown
keys via the "any new non-board keys" loop at `serialize_frontmatter:93`.
`monitor/monitor_app.py:1867` and `agentcrew/agentcrew_utils.py:62` only
select specific keys. **No spillover** — TUIs preserve the new fields
through edits without changes.

**Create/fold validation (wire into existing flows):**
- `aitask_create.sh` — when `--xdeps` / `--xdeprepo` (new batch
  flags) are supplied, validate: both-or-neither, `xdeprepo` resolves
  via `aitask_project_resolve.sh`, each `xdeps` number exists
  cross-repo side via `aitask_query_files.sh task-file --project <name> <N>`
  (returning `TASK_FILE:` or `NOT_FOUND`). Reuse `aitask_query_files.sh`
  with `--project` from t832_1.
- `aitask_fold_validate.sh` — ensure folded tasks don't lose `xdeps`
  references silently (warn if the primary task does not already include
  the folded task's `xdeprepo`).

**Tests:** `tests/test_xdeps_parser.sh` and `tests/test_xdeps_validation.sh`.

**depends:** `[t832_1]`

---

### t832_4 — Scope 2 completion: `xdeps` blocking logic

Extend `calculate_blocked_status()` at `.aitask-scripts/aitask_ls.sh:256-281`
to also check `xdeps`. After the existing in-repo `depends` loop:

```bash
# Check cross-repo dependencies (xdeps + xdeprepo)
if [[ -n "$xdeps_text" && -n "$xdeprepo_text" ]]; then
    IFS=',' read -ra XDEPS <<< "$xdeps_text"
    for xdep_id in "${XDEPS[@]}"; do
        local xdep_status
        xdep_status=$("$SCRIPT_DIR/aitask_query_files.sh" task-status \
            --project "$xdeprepo_text" "$xdep_id" 2>/dev/null | \
            sed 's/^STATUS://')
        if [[ "$xdep_status" != "Done" ]]; then
            blocked=1
            blocking_info="${blocking_info:+$blocking_info,}${xdeprepo_text}#${xdep_id}"
            break
        fi
    done
fi
```

Uses the `task-status` subcommand added in t832_1. **`Done` only** —
explicitly do NOT treat `Folded` or `Postponed` as satisfied (per user
decision).

**Sister-repo unavailable handling:** if the resolver returns `NOT_FOUND`
or `STALE`, the cross-repo call dies with a hint (per t832_1's policy). Catch
that case at the `aitask_ls.sh` call site and treat the task as `blocked`
with `blocking_info="<repo>#<id> (UNREACHABLE)"` so the user sees *why*
the task is blocked without crashing the lister.

**Board TUI surfacing of `xdeps` is owned by t832_8**, which depends
on this task for the blocking signal. Monitor TUI surfacing remains a
deferred follow-up (see Out of scope).

**Tests:** `tests/test_xdeps_blocking.sh` — two fake projects, cross-repo
task in each status, verify blocked vs unblocked correctly + UNREACHABLE
path.

**depends:** `[t832_1, t832_3]`

---

### t832_5 — Scope 3: parallel cross-repo planning procedure

**Location:** `.claude/skills/task-workflow/parallel-cross-repo-planning.md`
(shared module — per user decision, NOT a new skill family).

**Wire-in sites:** `.claude/skills/aitask-explore/SKILL.md.j2` and
`.claude/skills/aitask-create/SKILL.md.j2` planning sites. Trigger when
the user's prompt mentions a cross-repo project name or when the task body
contains `<name>#<id>` notation parsed via the
`^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$` regex from
`aidocs/cross_repo_references.md`.

**Procedure (5 steps):**

1. **Resolve both repos** via `aitask_project_resolve.sh` for each named
   project. Run codebase scans in **both** in parallel via the Explore
   subagent (one per repo) — each subagent gets the repo root and the
   focused question.
2. **Design paired child decompositions:** a single coordinated plan with
   the dependency graph spanning both repos. The graph is computed once;
   each repo's portion is materialized separately.
3. **Two parents, never one:** write two separate parent tasks — one per
   repo — each with its own children. Use regular `depends:` for in-repo
   edges and `xdeps:` + `xdeprepo:` for cross-repo edges.
4. **Numbering lockstep:** before writing either side, query both repos'
   next-free IDs via `aitask_query_files.sh task-file --project <name>
   <candidate>` in a loop. Reserve IDs cross-repo side via
   `aitask_create.sh --project <name> --batch ...` and capture the
   returned `TASK_CREATED:<id>:<path>` line. Then write local children
   with the now-known cross-repo IDs in their `xdeps:`.
5. **Driver symmetry:** the procedure produces identical output regardless
   of which repo is the driver.

**Commit-ordering protocol:**
- Local children land in the driver repo first (regular `./ait git commit`).
- Sister children land via `aitask_create.sh --project <name> --batch ...
  --commit` (the `--commit` flag means the the cross-repo project's own `./ait git` does
  the commit & push in its root).
- If the cross-repo `--commit` fails halfway (push error), the procedure must
  surface a clear "cross-repo side committed but did not push — run `cd
  <cross-repo-root> && ./ait git push`" warning rather than retrying silently.
  Document this failure mode explicitly in the procedure body.

**Rule (load-bearing):** never a single parent whose children straddle
two repos. Each repo's hierarchy stays locally complete and valid; only
the cross-repo edges are external. Encode the rule as a procedure
precondition with an explicit error message.

**Multi-agent porting:** per CLAUDE.md convention, implement Claude Code
first under `.claude/skills/task-workflow/`. Suggest separate aitasks to
port to Codex CLI (`.agents/skills/task-workflow/`), Gemini CLI
(`.gemini/skills/task-workflow/`), and OpenCode (`.opencode/skills/task-workflow/`).
Do NOT bundle the ports here.

**Tests:** mostly procedural — `./.aitask-scripts/aitask_skill_verify.sh`
+ a dry-run with two fake projects exercising the numbering lockstep
and the failure-mode warning.

**depends:** `[t832_1, t832_3, t832_7]` (parser for `xdeps` shape;
cross-repo update for bidirectional cross-edge wiring — see t832_7. Does
not need t832_4's blocking logic to operate; the procedure only needs to
*write* the xdeps fields correctly, not evaluate them.)

---

### t832_7 — Scope 1c: cross-repo task update (`aitask_update.sh --project <name>`)

Mirror of `aitask_create.sh --project` for the update mutation surface.
Without this, the parallel-planning procedure (t832_5) cannot wire
**symmetric** cross-edges (where both sides have `xdeps:` pointing at
each other), because of the chicken-and-egg ID dependency:

1. Create local children L1..Ln first (regular `aitask_create.sh`).
2. Create cross-repo children S1..Sn with `aitask_create.sh --project B
   --xdeps L1,L2 --xdeprepo A` (the now-known local IDs go into cross-repo
   children at create time).
3. **Update local children** to add `xdeps: [S1, S2] xdeprepo: B` (the
   now-known cross-repo IDs).

Step 3 is where this child earns its keep.

**Pattern (copy from `aitask_create.sh:1693-1753`):**

- Parse `--project <name>` out of argv before subcommand dispatch.
- Resolve via `aitask_project_resolve.sh`; die-with-hint on `STALE`/`NOT_FOUND`.
- On success: `cd "$root"; exec "$root/.aitask-scripts/aitask_update.sh" "${forwarded[@]}"`.

**Required guardrails (unlike create):**

- `--project` requires `--batch` (mirror create's restriction).
- Lock check: refuse the cross-repo update if the cross-repo task is locked
  by a *different* host/email — fail with a clear "cross-repo task t<N> is
  locked by <owner>@<hostname>; cannot update from this host". The local
  flow can mutate the file but cannot acquire the cross-repo task's lock cleanly;
  silently overwriting a lock-held task corrupts the multi-PC reclaim
  signal. Use `aitask_lock.sh --check <N>` (re-exec'd in cross-repo context)
  to read the lock state.
- Status transitions allowed cross-repo: the administrative subset only —
  `--xdeps`, `--xdeprepo`, `--labels`, `--priority`, `--effort`,
  `--depends`, `--postpone`, `--assigned-to`. Refuse cross-repo
  `--status Implementing` and `--status Done`; those should always go
  through the the cross-repo project's own `/aitask-pick` workflow (which handles lock
  acquisition, plan externalization, and archival in one place). This
  guardrail keeps cross-repo update **administrative**, not workflow-
  bypassing.

**Out of scope explicitly:**
- Cross-repo archive (split-brain risk; covered above).
- Cross-repo `--fold` (folding requires reading both task bodies + a
  primary task to fold *into*; cross-repo folding semantics are
  unsettled — defer until parallel-planning procedure dogfooding
  reveals whether it's actually needed).

**Tests:** `tests/test_update_cross_repo.sh` — synthesize two fake
projects, verify successful cross-repo update of allowed fields, verify
the refused-for-locked / refused-for-status-transition guardrails fire
correctly.

**depends:** `[t832_1]` (uses the same re-exec pattern; only depends on
t832_1 for the resolver-conventions being shipped + tests for the same
fake-project harness.)

---

### t832_8 — `ait board` TUI cross-repo support

Surface `xdeps` / `xdeprepo` in `aitask_board.py` task cards and the
blocked-status display, and parse the `aitasks#N_M` notation regex from
`aidocs/cross_repo_references.md` in task body text so cross-repo
references are navigable from the board.

**Three concerns bundled (kept together — the TUI changes are coupled):**

1. **Card display:** when a task has `xdeps:` + `xdeprepo:`, render the
   cross-repo dependency line with the `<repo>#<id>` form (e.g.,
   `xdeps: aitasks_mobile#42, aitasks_mobile#16_2`). Visually distinguish
   from local `depends:`.
2. **Blocked-status surfacing:** if t832_4's blocking-logic flags a task
   as blocked by a cross-repo dep, render a distinct "blocked by
   cross-repo" indicator (separate from the regular "blocked by local").
   Show the cross-repo target's status inline if cheap to fetch
   (`aitask_query_files.sh task-status --project <name> <id>` from
   t832_1), with a graceful fallback to "UNREACHABLE" matching t832_4's
   error path.
3. **Cross-repo notation parser + navigation:** when the user activates
   an `aitasks#N_M` reference inside a task body / plan body shown in
   the board, resolve the project name via `aitask_project_resolve.sh`
   and open the cross-repo task content read-only (no edit, no lock
   acquisition). Closing the popup returns to the current board session.
   This deliberately stops short of *switching* the board to the
   cross-repo project — that's a separate UX question (see Out of scope
   below).

**Key files:**
- `.aitask-scripts/board/aitask_board.py` (display + key handlers).
- `.aitask-scripts/board/task_yaml.py` (already round-trips unknown
  keys via `serialize_frontmatter` — `xdeps`/`xdeprepo` will already be
  preserved by t832_3's parser changes; no new YAML work needed here).
- A new minimal notation parser, e.g.
  `.aitask-scripts/lib/cross_repo_notation.py`, exposing
  `parse(text) → list[(project, task_id)]` using the
  `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$` regex. Shared so future
  TUI/script consumers don't reinvent it.

**Out of scope (defer):**
- **`ait monitor` cross-repo surfacing** — separate follow-up after
  this lands and its UX patterns settle.
- **Switching the board to a cross-repo project session** (full TUI
  re-mount with a different `TASK_DIR`) — UX is unsettled; the
  read-only popup is the minimum viable navigation.
- **In-board editing of cross-repo tasks** — cross-repo updates go
  through `aitask_update.sh --project <name>` (t832_7) at the script
  level; the TUI does not call it directly until UX is settled.

**Tests:** `tests/test_cross_repo_notation.sh` (parser unit tests).
TUI display verification is by manual run (`ait board` against a fake
two-project setup) since `aitask_board.py` is interactive — flag this
as a `manual_verification` sibling candidate if the parent's child task
checkpoint reveals more than this task warrants alone.

**depends:** `[t832_3, t832_4]` (parser for the field shape; blocking
logic for the "blocked by cross-repo" signal). Does NOT depend on
t832_5 or t832_7 — the board only displays/navigates; it does not
create or update cross-repo tasks.

---

### t832_6 — Retrospective dogfooding evaluation

Drive a real coordination task between `aitasks` and `aitasks_mobile`
end-to-end using the now-shipped plumbing. Document outcomes in the
plan's Final Implementation Notes:

- **Did the re-exec contract feel right?** Any unanticipated subcommand
  shapes that needed bespoke handling?
- **`xdeps` blocking UX in board (t832_8):** does the read-only-popup
  navigation model carry its weight, or do users want a full
  project-switch? Does the "blocked by cross-repo" indicator surface
  often enough to matter visually?
- **Parallel-planning procedure friction:** numbering-lockstep race
  conditions? Commit-ordering rough edges (cross-repo push failures, partial
  rollback needs)?
- **Notation gap:** does the `aitasks#N_M` notation parser carry its
  weight, or is `xdeps:`/`xdeprepo:` doing all the load-bearing
  work in practice?

**Deliverable:** the audit document itself + zero-to-N targeted follow-up
tasks for confirmed friction. Per `aidocs/planning_conventions.md` rule
"Audit-only tasks with zero findings produce audit-only plans": if no
friction surfaces, the deliverable is just the documented audit + "no
follow-ups needed."

**depends:** `[t832_1, t832_2, t832_3, t832_4, t832_5, t832_7, t832_8]`

---

## Out of scope (preserved from parent task — do not silently absorb)

- **`ait monitor` cross-repo surfacing** — separate follow-up after
  t832_8 (board) lands and its UX patterns settle. (`ait board` cross-repo
  support IS in scope as t832_8.)
- **Cross-project parent linkage (`--project X --parent Y`)** — explicitly
  excluded by t826_1 and re-confirmed here; the parallel-planning model
  is "two parents, one per repo".
- **Auto-clone of `NOT_FOUND` cross-repo projects from `git_remote`** — t826_5
  scope.
- **Cross-repo merge coordination / transactional commits** — carried
  over from parent brainstorm t826.
- **`aitask_revert_analyze.sh` cross-repo** — defer to a separate task if
  cross-attribution ever becomes needed.

## Implementation steps for t832 itself (this task)

t832 is a brainstorm — its concrete output is the children, not code.

1. Apply the user-confirmed design decisions (settled above).
2. Create children t832_1 through t832_8 via the **Batch Task Creation
   Procedure** (`task-creation-batch.md`), each with:
   - `--parent 832`
   - `--name <slug>` matching the child purpose
   - `--type feature` (all eight are feature work)
   - `--priority medium`
   - `--effort` per below
   - `--depends "<csv of sibling IDs>"`
   - `--desc-file <inline content>` matching the child sections above —
     each child task description MUST include the Context, Key Files,
     Implementation Plan, and Verification sections per CLAUDE.md and
     the planning workflow.
3. Effort estimates:
   - t832_1: medium (uniform re-exec across 3 helpers + 1 new subcommand)
   - t832_2: medium (different pattern; aggregation logic)
   - t832_3: low-medium (parser is trivial; validation is the real work)
   - t832_4: low (single function extension + test)
   - t832_5: high (new shared procedure + wire-in sites + commit-ordering)
   - t832_6: low (audit/document)
   - t832_7: low-medium (re-exec mirror + guardrails for lock/status)
   - t832_8: medium-high (TUI display + notation parser + navigation popup)
4. Write implementation plans for ALL eight children to `aiplans/p832/`
   before proceeding (per planning workflow's child-task documentation
   requirements).
5. Revert t832 status to `Ready` (parent gets the "Has children" display
   automatically) and release the parent lock.
6. **Manual-verification sibling:** offer one covering t832_8 (and any
   other TUI-touching children that surface). The board TUI's display +
   navigation flow needs human eyes; bash tests + skill-verify can't
   confirm UX. The post-children-creation checkpoint in `planning.md`
   step 6.1 will prompt for this; accept the "aggregate sibling covering
   all children" option scoped to `[832_8]` (since t832_8 is the only
   TUI-touching child).
7. **Child task checkpoint:** present "Start first child" / "Stop here"
   (always-interactive checkpoint per workflow).

## Verification

For t832 itself:

- All 8 child task files exist under `aitasks/t832/` with correct
  `depends:` graphs matching the diagram in **Decomposition**.
- All 8 plan files exist under `aiplans/p832/` with the required metadata
  headers (parent task, sibling tasks, archived sibling plans, worktree,
  branch, base branch).
- `aitask_ls.sh -v --children 832 99` shows all 8 with correct
  Ready/Blocked status (1 is unblocked; 2-8 are blocked transitively).
- Manual-verification sibling (if accepted at checkpoint) is created
  scoped to `[832_8]`.
- `./.aitask-scripts/aitask_skill_verify.sh` passes (no skill changes in
  t832 itself; the rendered SKILL.md files are unchanged).
- Children's individual verification is owned by their own plans.

## References

- Foundation: `aiplans/archived/p826/p826_1_*` (registry + resolver +
  `ait projects` + `--project` flag).
- Authoring aidoc: `aidocs/cross_repo_references.md` — registry schema,
  resolver protocol, `aitasks#N` notation regex, current
  "what is NOT in scope" list.
- Re-exec pattern reference: `.aitask-scripts/aitask_create.sh:1693-1753`.
- Sibling t826 children (independent): t826_2 (TUI switcher), t826_3
  (website docs), t826_4 (manual verification), t826_5 (stale-registry
  UX brainstorm).
- Origin pain example:
  `aitasks_mobile/aitasks/archived/t13/t13_2_sister_qr_add_hostname_field.md`.
