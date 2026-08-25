---
Task: t1599_2_scope_fold_mark_commit_and_guard_amend.md
Parent Task: aitasks/t1599_scope_task_data_commits_to_their_own_paths.md
Sibling Tasks: aitasks/t1599/t1599_1_*.md, aitasks/t1599/t1599_3_*.md, aitasks/t1599/t1599_4_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# p1599_2 — Scope `aitask_fold_mark.sh` and make its amend fail loudly

## Context

Highest **rate** of the three primary t1599 sites: **5 of 11** fold commits on
the live `aitask-data` branch carry a foreign path. Example `8664a6a76`
("Fold tasks into t1515: merge t1285") also committed
`aitasks/t1467_cross_agent_phase_prompt_detection.md`.

Volume is low, but the `--amend` path is the most dangerous code in the whole
parent task — it can rewrite an already-pushed commit.

Owns `.aitask-scripts/aitask_fold_mark.sh` exclusively.

## Step 1 — Reuse the path set that already exists

`rollback_paths` (`:567-580`) is **exactly** the set this commit should touch:
primary file, folded files, transitive files, parent files of folded children
(the `--remove-child` / `children_to_implement` edit at `:352`), and rebound
attachment-meta relpaths. It is used only for rollback today.

Reuse it as the commit pathspec. **No new derivation logic.**

## Step 2 — Scope `fresh` (`:590-614`)

- `task_git add aitasks/` → `task_git add -- "${rollback_paths[@]}"`. The
  separate `fold_meta_relpaths` add becomes redundant (already appended at
  `:578-580`).
- Add `-- "${rollback_paths[@]}"` to the commit; `-m` before `--`.
- Scope the `elif task_git diff --cached --quiet` no-op branch at `:607` to
  `task_git status --porcelain -- "${rollback_paths[@]}"`.
- Guard an empty `rollback_paths` — `commit --` with no pathspec commits the
  whole index.

## Step 3 — Guard `amend` (`:615-626`)

Today this is a bare `task_git commit --amend --no-edit` against **whatever HEAD
happens to be** — no hash argument, no ancestry check, no authorship check. The
callers that pass `--commit-mode amend` merely *assume* the previous step created
the task commit.

If HEAD already carries foreign files, `--amend` rewrites it to
(everything already in it) ∪ (everything newly staged): the foreign files are
silently retained, re-attributed under the fold message via `--no-edit`, and
their SHA changes. If already pushed, that rewrites published history — and
`aitask_sync.sh` pushes non-force, so the next sync fails with
`ERROR:push_failed`.

Add the pre-amend refusal from the task file. Two implementation cautions:

- Under `set -euo pipefail`, an empty `rollback_paths` makes the `grep -vxF -f`
  pattern file empty, which matches everything. Guard the empty case explicitly.
- The guard must run **before** any staging, so a refusal leaves no residue.

Then scope the amend itself as in `fresh`.

## Adjacent findings — RECORD in Final Implementation Notes, do not fix

- `amend` has no no-op branch (unlike `fresh`), so an amend with nothing newly
  staged still rewrites the commit and prints `AMENDED`.
- `_fold_rollback` (`:583-586`) restores only `rollback_paths`, so a failed
  commit that had staged foreign files left them staged. Scoping makes this moot.
- `--commit-mode` is validated only at `:630-632` — **after** every mutation has
  already been written to disk.

## Verification

Extend `tests/test_fold_mark.sh`:

- Bystander not swept, `fresh` mode — commit contains only the fold's own paths;
  bystander still ` M` unstaged.
- Bystander not swept, `amend` mode — with a clean HEAD the guard permits it.
- **Amend refuses on a foreign HEAD** — non-zero exit, the error names the
  offending path, and `git rev-parse HEAD` is **unchanged**.
- **Child fold still commits the parent file** — fold a child id `P_C` and assert
  the parent `tP_*.md` IS in the commit. It is a legitimate co-change; this is
  the case a naive "only the primary task file" scoping would wrongly drop.
- `--commit-mode none` still prints `NO_COMMIT` and creates no commit.

**Negative controls (required):** each bystander assertion must FAIL against the
pre-fix `add aitasks/`; the amend-refusal test must FAIL (HEAD gets rewritten)
against the pre-fix bare amend.

`shellcheck .aitask-scripts/aitask_fold_mark.sh`.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.
