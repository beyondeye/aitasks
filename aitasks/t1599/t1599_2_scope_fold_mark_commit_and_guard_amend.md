---
priority: high
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness, task_metadata]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
implemented_with: claudecode/opus5
created_at: 2026-08-25 12:48
updated_at: 2026-09-01 10:13
---

## Context

Parent: t1599 — framework helpers stage a whole directory and commit the entire
git index, sweeping another live session's in-flight files into a commit whose
message names a different task.

`aitask_fold_mark.sh` has the **highest swallow rate** of the three primary
sites: **5 of 11** fold commits on the live `aitask-data` branch carry a foreign
path (measured allowing every task id named in the subject plus their parents).
Example: `8664a6a76` "ait: Fold tasks into t1515: merge t1285" also committed
`aitasks/t1467_cross_agent_phase_prompt_detection.md`.

Volume is low (11 folds ever), but the `--amend` path is the most dangerous code
in the whole parent task: it can rewrite a commit that has already been pushed.

## Exclusive script ownership

This child owns **`.aitask-scripts/aitask_fold_mark.sh`** and nothing else.
Do NOT edit `aitask_pick_own.sh` (t1599_1), `aitask_sync.sh` / `aitask_lock.sh`
(t1599_3), or the sweep targets owned by t1599_4.

## Key files to modify

- `.aitask-scripts/aitask_fold_mark.sh` — Step 6 commit block at `:588-633`.
- `tests/test_fold_mark.sh` — extend.

## The good news: the exact path set already exists

`rollback_paths` is built at `:567-580` and is **precisely** the set this commit
should touch:

1. `$primary_file` — the primary task's `.md` (mutated at `:331-338` and
   possibly `:447-450` / `:507-508` for attachments/artifacts)
2. `${folded_files[@]}` — each directly folded task's `.md` (mutated at `:345`)
3. `${transitive_files[@]}` — transitively folded tasks (mutated at `:361`)
4. **parent files of folded children** — for any folded id matching
   `^([0-9]+)_([0-9]+)$`, the parent `t<P>_*.md`, resolved at `:574` and mutated
   at `:352` via `--remove-child` (the `children_to_implement` edit)
5. `${fold_meta_relpaths[@]}` — rebound attachment-ledger meta files, appended
   at `:578-580`

It is currently used **only** for rollback. Reuse it as the commit pathspec — no
new derivation logic is needed.

## Step 1: Scope the `fresh` mode (`:590-614`)

Current:

```bash
    fresh)
        task_git add aitasks/ >/dev/null 2>&1 || true
        if (( ${#fold_meta_relpaths[@]} > 0 )); then
            task_git add -- "${fold_meta_relpaths[@]}" >/dev/null 2>&1 || true
        fi
        ...
        if task_git commit -m "ait: Fold tasks into t${primary_id}: merge ${joined}" --quiet >/dev/null 2>&1; then
```

Replace `task_git add aitasks/` with `task_git add -- "${rollback_paths[@]}"`
(which already includes the meta relpaths, so the separate meta `add` becomes
redundant), and add `-- "${rollback_paths[@]}"` to the commit. Note `-m` must
precede `--`.

The `elif task_git diff --cached --quiet` no-op branch at `:607` is index-wide
and must be scoped too — use
`task_git status --porcelain -- "${rollback_paths[@]}"` (the
`aitask_gate.sh:1025-1032` shape).

Guard against an empty `rollback_paths`: `commit --` with no pathspec commits
the whole index, re-creating the bug.

## Step 2: Make `--amend` fail loudly (`:615-626`)

Current:

```bash
    amend)
        task_git add aitasks/ >/dev/null 2>&1 || true
        ...
        if task_git commit --amend --no-edit --quiet >/dev/null 2>&1; then
            echo "AMENDED"
```

This is a bare amend of **whatever HEAD happens to be** — no hash argument, no
ancestry check, no authorship check, no "is this my commit" guard. The callers
that pass `--commit-mode amend` (`aitask-pr-import-*/SKILL.md:252`,
`aitask-explore-*/SKILL.md:301`, `aitask-contribution-review/SKILL.md:249`)
*assume* the immediately preceding step created the task commit, but nothing
verifies it.

If that commit already carries foreign files, `--amend` rewrites it to
(everything already in it) ∪ (everything newly staged): the foreign files are
silently retained, re-attributed under the fold message via `--no-edit`, and
their SHA changes. If it was already pushed, this rewrites published history —
and `aitask_sync.sh` does a plain non-force push, so the next sync fails with
`ERROR:push_failed`.

Add a pre-amend guard that refuses rather than rewriting:

```bash
foreign="$(task_git show --name-only --format='' HEAD | grep -v '^$' \
    | grep -vxF -f <(printf '%s\n' "${rollback_paths[@]}") || true)"
[[ -z "$foreign" ]] || die "refusing --commit-mode amend: HEAD ($(task_git rev-parse --short HEAD)) carries paths outside this fold:
$foreign
Re-run with --commit-mode fresh."
```

Then scope the amend itself the same way as `fresh`.

Note `grep -vxF -f -` needs care under `set -euo pipefail`: an empty
`rollback_paths` makes the pattern file empty and `grep -vxF -f /dev/null`
matches everything. Guard the empty case explicitly.

## Adjacent findings — RECORD, do not fix here

Note these in the plan's Final Implementation Notes; they are out of scope:

- `amend` has **no** `diff --cached --quiet` no-op branch (unlike `fresh`), so an
  amend with nothing newly staged still rewrites the commit and prints
  `AMENDED`.
- `_fold_rollback` (`:583-586`) restores only `rollback_paths`, so a failed
  commit that had staged foreign files left them staged. Scoping makes this
  moot, which is why it is not fixed separately.
- `--commit-mode` is validated only at `:630-632`, i.e. **after** every mutation
  has already been written to disk.

## Verification

Extend `tests/test_fold_mark.sh`. Fixture patterns: `tests/test_fold_mark.sh`
itself, plus `tests/test_fold_content.sh` / `tests/test_fold_validate.sh`.

- **Bystander not swept, `fresh` mode:** seed an unrelated dirty task file, fold
  t_a into t_b, assert `git show --name-only --pretty=format: HEAD` contains only
  the fold's own paths and that the bystander is still ` M` unstaged.
- **Bystander not swept, `amend` mode:** same, with a clean HEAD that contains
  only fold-set paths so the guard permits the amend.
- **Amend refuses on a foreign HEAD:** seed HEAD with a commit containing a
  foreign file, run `--commit-mode amend`, assert a **non-zero exit**, that the
  error names the offending path, and — critically — that
  `git rev-parse HEAD` is **unchanged** (the commit was not rewritten).
- **Child fold still commits the parent file:** fold a child id `P_C` and assert
  the parent `tP_*.md` (the `children_to_implement` edit) IS in the commit —
  it is a legitimate co-change, not a swallow. This is the case a naive
  "only the primary task file" scoping would wrongly drop.
- **`--commit-mode none`** still prints `NO_COMMIT` and creates no commit
  (`rev-list --count` unchanged, the `tests/test_gate_record.sh:100-107` idiom).

**Negative control (required).** Each bystander assertion must FAIL against the
pre-fix `task_git add aitasks/`, and the amend-refusal test must FAIL (HEAD gets
rewritten) against the pre-fix bare amend.

Test conventions per `tests/test_lock_force.sh`; source
`tests/lib/test_scaffold.sh` then `tests/lib/asserts.sh`. Assertion argument
order is `assert_contains <desc> <needle> <haystack>`. If any test body runs
inside a `( … )` subshell, opt into the file-backed counters
(`assert_counters_init` + `assert_counters_load`) per CLAUDE.md.

Also run `shellcheck .aitask-scripts/aitask_fold_mark.sh`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T07:13:47Z status=pass attempt=1 type=human
