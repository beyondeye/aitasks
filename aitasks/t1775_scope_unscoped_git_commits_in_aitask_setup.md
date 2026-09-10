---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
anchor: 1762
followup_kind: upstream_defect
created_at: 2026-09-10 11:46
updated_at: 2026-09-10 11:46
---

## Origin

Spawned from t1762 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:1973 — plain unscoped git commit against the user's project worktree (also :1975, :2304, :2336, :2368, :2414, :2448); :1973/:1975 are gated by a global git diff --cached --quiet, so a foreign pre-staged file both triggers the commit and rides along; the same file already does it right at :3783`

## Diagnostic context

t1762 scoped the plain `git commit` sites on `main` at the **instruction** layer
(skill procedures and aidocs) and deliberately left the shell layer out of scope.
Its sweep found these seven `git commit` calls in `aitask_setup.sh` that run
against the user's project worktree with no `--` pathspec:

- `:1973` `git commit -m "ait: Migrate task data to aitask-data branch"` and
  `:1975` `git commit -m "ait: Configure task data branch with worktree and symlinks"`
  — after `git add "${files_to_add[@]}"`, gated by a **global**
  `git diff --cached --quiet`. A foreign pre-staged file both makes the gate fire
  and rides along in the commit.
- `:2304`, `:2336`, `:2368`, `:2414`, `:2448` —
  `(cd "$project_dir" && git add .gitignore && git commit -m "ait: Add … to .gitignore (…)" 2>/dev/null) || true`.
  The `add` is scoped, the commit is not, so whatever the user had staged is
  swept into an `ait:` commit under a framework message.

The same file already has the correct shape at `:3783` —
`git commit -m "ait: Add aitask framework" -- "${changed_files[@]}"` — with a
comment saying a bare commit would sweep a foreign pre-staged index.

Verified NOT in scope: `:1818`/`:1820` run inside the data worktree after
`git add .`; the `aitask_crew_*.sh` commits run inside dedicated crew worktrees.
Neither shares the user's index.

Measured semantics (t1762, scratch repos), relevant to the fix:

- `git commit -- <paths>` is a partial commit: it takes the named paths'
  worktree content and ignores the index for everything else. A tracked path
  needs no `add`.
- An empty pathspec (`git commit -m x --` with nothing after it) commits the
  **whole** index — guard any computed list before committing.
- A partial commit is refused during a merge
  (`fatal: cannot do a partial commit during a merge`).

## Related (separate) work

- t1747_4 fixes the fail-open baseline probe in `_ait_list_framework_changes`
  (`~:3584-3597`) that feeds `commit_framework_files` — same file and defect
  family, but not these seven sites.
- t1357_1 is about to extend the `.gitignore`-population block modelled on the
  `.aitask-gates` entry at `:2368`. If it lands before this task, it adds an
  eighth site of the same unscoped shape; re-sweep before starting.

## Suggested fix

Give each of the five `.gitignore` sites `-- .gitignore`. Give `:1973`/`:1975`
`-- "${files_to_add[@]}"` and narrow their gate to the same pathspec
(`git diff --cached --quiet -- "${files_to_add[@]}"`), so a foreign staged file
neither triggers nor joins the commit. `tests/test_no_unscoped_task_commit.sh`
does not scan plain `git commit` under `.aitask-scripts/` (it would fire on every
legitimate commit there); decide whether a check targeted at `$project_dir`
commits is feasible, and record the decision either way.
