---
Task: t2120_fix_unverified_refusal_rerun_recovery_hint.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2120 — Recovery hints after a refused/failed framework commit: manual, path-scoped commit — not a re-run, not a bare commit

## Context

`aitask_setup.sh` and `install.sh` both snapshot the pre-run dirty state of the
framework paths and, at commit time, subtract it: anything dirty before the run
is "left alone (not committed)". So when a run leaves its own files uncommitted
(an unverified-baseline refusal, or a failed `git add`), a **re-run** snapshots
those files as pre-existing and never commits them (verified for install in
t2116; setup has the identical `snapshot_pre_setup_dirty` →
`commit_framework_files` / `_ait_subtract` logic, `aitask_setup.sh:4430-4555`).
The only recovery that works is a manual commit.

That manual commit must also be **path-scoped**. The automated commits pass
explicit pathspecs precisely because a bare `git commit` commits the whole
index, sweeping in anything someone else had already staged (comments at
`aitask_setup.sh:~4610`, `install.sh:~1495`). Every manual-recovery hint today
names a bare `git commit` (or worse, `git add -A`), recommending the exact sweep
the code avoids.

Defective hints (line numbers as of HEAD 0b18f4cd7 — grep the strings):

| site | current text | flaw |
|---|---|---|
| setup `_ait_refuse_unverified_commit` (+ header comment) | "Re-run 'ait setup' once git works again, or commit … yourself with $recovery" | re-run can't recover; `$recovery` bare |
| setup callers of it (4 sites) | `$recovery` = `'git add' / 'git commit'`, `'./ait git add' / './ait git commit'` | bare commit |
| install `_install_refuse_unverified_commit` callers (5 sites) | `'git add' / 'git commit'`, `'git -C .aitask-data add' / '… commit'` | bare commit |
| install `commit_installed_files` `git add` failure | "Run 'ait setup' to retry." | re-run can't recover |
| setup `commit_framework_files` `git add` failure | "Run 'git add -A && git commit' manually." | sweeps whole tree + index |
| setup + install "staged but NOT committed" (main) | "Run 'git commit' manually." | bare commit sweeps foreign staged files |
| setup declined-commit branches (main + data) | "You can manually commit later with 'git add' and 'git commit'." / './ait git …' | bare commit |
| setup `commit_framework_files` post-commit `still_untracked` warning | "…then 'git add -A && git commit' to finalize." | sweeps whole tree + index |
| install `commit_installed_files` post-commit `still_untracked` warning | "…then 'git add' and 'git commit' to finalize." | bare add/commit |

The inventory above comes from grepping every `warn`/`info`/`die` string plus
every `$recovery` argument in both files for `git add` / `git commit` (the
earlier, phrase-specific greps missed the two `still_untracked` warnings).

Not changed: "Framework data files NOT committed." / "… staged but NOT
committed." (data branch) carry no recovery command, so they recommend nothing
wrong; "Review and commit them yourself when ready." refers to the user's own
pre-existing changes, not framework files.

No test pins any of the old wordings (grepped `tests/`, `website/content`,
`aidocs`, `.claude/skills`). Wording-only change — no new recovery machinery.

Work on the current branch (profile `fast`).

## Changes

One phrasing used at every site: **commit only the framework files you
reviewed, naming each path**, with commands shown as `<cmd> -- <path>...`, plus
the reason where a bare commit is the natural mistake ("a commit without paths
also commits anything else already staged"). The caution deliberately never
quotes a bare command: any quoted `'git commit'` / `'git add'` with no pathspec
is exactly what the verification audit flags, so the messages must not contain
one even as a warning example.

### `.aitask-scripts/aitask_setup.sh`

- `_ait_refuse_unverified_commit` header comment: mirror install's (own leftover
  files are recoverable **by hand**; a re-run's snapshot would treat them as
  pre-existing and leave them alone) and add that the manual commit must name
  its paths. Body info line →
  `info "Once git works again, review 'git status' and commit only the framework files you reviewed, naming each path: $recovery — a commit without paths also commits anything else already staged."`
- Its four callers' `$recovery` →
  `"'git add -- <path>...' / 'git commit -- <path>...'"` (main) and
  `"'./ait git add -- <path>...' / './ait git commit -- <path>...'"` (data).
- `commit_framework_files` `git add` failure →
  `warn "Framework files NOT committed. Review 'git status' and commit only the framework files you reviewed, naming each path: 'git add -- <path>...' / 'git commit -- <path>...'."`
- `commit_framework_files` commit failure →
  `warn "Framework files staged but NOT committed. Commit them yourself naming each path — 'git commit -- <path>...'; a commit without paths also commits anything else already staged."`
- Declined-commit branches →
  `info "You can commit them later, naming each path: 'git add -- <path>...' / 'git commit -- <path>...'."`
  and the data twin with `'./ait git add -- <path>...' / './ait git commit -- <path>...'`.
- `commit_framework_files` post-commit `still_untracked` warning (the file
  list is printed just above it) →
  `warn "Run 'git status' to investigate, then commit only the listed files you intend, naming each path: 'git add -- <path>...' / 'git commit -- <path>...'."`

### `install.sh`

- `_install_refuse_unverified_commit`: same body/comment wording as the setup
  helper (keeps the twins identical).
- Its five callers' `$recovery` →
  `"'git add -- <path>...' / 'git commit -- <path>...'"` (main) and
  `"'git -C .aitask-data add -- <path>...' / 'git -C .aitask-data commit -- <path>...'"` (data).
- `commit_installed_files` `git add` failure →
  `warn "Framework files NOT committed. Review 'git status' and commit only the framework files you reviewed, naming each path: 'git add -- <path>...' / 'git commit -- <path>...' — re-running 'ait setup' would leave them alone as pre-existing changes."`
- `commit_installed_files` commit failure → same text as the setup twin.
- `commit_installed_files` post-commit `still_untracked` warning → same text as
  the setup twin.

### Tests

`tests/test_setup_failopen_probes.sh` case 2 (commit-time list probe fails →
refused), on the existing `$output`:
- `assert_contains "2: refusal names a path-scoped commit" "git commit -- <path>" "$output"`
- `assert_not_contains "2: refusal does not send the user to a re-run" "Re-run 'ait setup'" "$output"`

`tests/test_install_failopen_probes.sh` case 2: the same `assert_contains`.
Setup case 3 (data refusal): `assert_contains "3: data refusal names a path-scoped commit" "./ait git commit -- <path>" "$output"`.

All three positive assertions are red against the current wording (test edits
land before the source edits). The `git add`/commit-failure and declined
branches have no existing harness and get no new test.

## Verification

```bash
bash tests/test_setup_failopen_probes.sh      # first against unedited sources → new asserts FAIL
bash tests/test_install_failopen_probes.sh
shellcheck .aitask-scripts/aitask_setup.sh install.sh
# Any quoted add/commit command ending without a pathspec, whatever prose
# surrounds it ("with", "then", "/"), plus the -A sweep and the re-run hints:
grep -nE "(git|ait git|\.aitask-data) (add|commit)'|git add -A|Re-run 'ait setup' once git works|Run 'ait setup' to retry" \
  .aitask-scripts/aitask_setup.sh install.sh | grep -vE '^[^:]+:[0-9]+:[[:space:]]*#'   # expect none
```

Run against the current tree, this pattern hits exactly 18 lines (install 8, setup 10), which are all the table's sites
(including install's "then 'git add' and 'git commit'" line) and nothing else.
The narrowing leaves out setup's three "Re-run 'ait setup' once the fetch …"
data-branch hints, which are correct (a re-run does reconcile there), and the
`git add -A` comment at setup:~2858. So an empty result after the edit
means every site was fixed. The 10 proposed message/argument strings in this
plan were also passed through the same pattern: they produce no matches, so the
fix itself does not trip the audit.

Then Step 9 (Post-Implementation): commit, archive t2120.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
