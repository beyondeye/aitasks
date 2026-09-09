---
Task: t1747_3_sync_authorization_probes.md
Parent Task: aitasks/t1747_sweep_failopen_git_probes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1747_3 — Four fail-open authorization probes in `aitask_sync.sh`

## Context

Audit rows A3, A4, A5, A10 (see `aidocs/framework/failopen_git_probes.md`).
Grouped because they share one file and one test harness; each still gets its
own control. Verify every line number against the tree before editing — they
were taken at t1747 planning time.

## Implementation

### A3 — `:772` shared-index staged guard (`_commit_group`)

```bash
    staged="$(task_git diff --cached --name-only -- "${paths[@]}" 2>/dev/null)" || staged=""
    if [[ -n "$staged" ]]; then _protect "staged_elsewhere" …; return 0; fi
```

A failed probe reads as "nobody staged anything" and the group proceeds to
`task_git add` / `commit -o` / the failure-path `reset` (:817). The harm is named
in the code's own comment: *"`add` would replace it and `reset` would remove it,
destroying in-flight work."* The guard is disarmed by exactly the condition
(index contention) that makes the hazard likely.

**Disposition:** capture the rc; unverified ⇒ `_protect "staged_unverified"` and
defer the group, the same outcome as a positive detection. Deferral is already
this function's safe answer — it is what `_protect` exists for.

### A4 — `:503` quarantine-release settlement clause

```bash
               && [[ -z "$(task_git status --porcelain -- "$p" 2>/dev/null)" ]]; then
                iinfo_err "quarantine released (owner gone, state settled): $p"; continue
```

Substitution failure is invisible inside `[[ -z … ]]`, so an **unreadable**
worktree reads as clean ⇒ the entry is dropped from `QUARANTINE_HELD` /
`PUBLICATION_BLOCKED` and a commit the framework deliberately withheld is
pushed. The comment above argues that a clean worktree is not settlement on its
own; this closes the matching hole for an unreadable one.

**Disposition:** hoist the probe out of the `[[ ]]`, capture its rc; unverified
⇒ **hold** (fall through to `QUARANTINE_HELD`). Age never releases here, and
neither should an unread probe.

### A5 — `:919` conflict-vs-other-error classifier (`do_pull_rebase`)

```bash
        conflicted=$(task_git diff --name-only --diff-filter=U 2>/dev/null || true)
        if [[ -n "$conflicted" ]]; then … else <abort + ERROR:pull_rebase_failed> fi
```

Empty reads as "not a conflict" ⇒ aborts a real in-progress conflict resolution.
Recoverable via `ORIG_HEAD`, but it silently discards merge work.

**Disposition:** unverified ⇒ a **distinct** batch token / diagnostic rather than
the generic `ERROR:pull_rebase_failed`, so the caller can tell "this was not a
conflict" from "we could not tell". Check every consumer of the existing token
before adding a new one — `batch_out` values are a wire contract.

### A10 — `:301` `_sync_gitdir` silent `.git` fallback

```bash
_sync_gitdir() {
    local gd; gd="$(_ait_data_gitdir)"
    if [[ -z "$gd" ]]; then gd="$(git rev-parse --git-dir 2>/dev/null)" || gd=".git"; fi
    printf '%s' "${gd:-.git}"
}
```

A fabricated `.git` makes every `[[ -e "$gd/rebase-merge" ]]` test miss ⇒
`_worktree_wedged` reads "not wedged" ⇒ sync proceeds to auto-commit and push
over a wedged worktree. It **also** relocates `_quarantine_path`, and
`_quarantine_load` returns early on a missing/empty file
(`[[ -s "$qf" ]] || return 0`), so **every held quarantine entry is silently
lost** — releasing withheld commits for publication by accident.

**Disposition:** an unresolvable git-dir is **unverified** ⇒ refuse at the
helper. Never substitute a default that composes into a path — that is the same
shape as `[[ -f "/MERGE_HEAD" ]]` in t1747_6.

**This is the call-site case.** `_sync_gitdir` has two direct consumers
(`_worktree_wedged:343`, `_quarantine_path:306`), and `_quarantine_path` fans out
to four more. Decide each one's behaviour on "unverified" — a wedge check that
cannot read the git-dir must **refuse to sync**, and a quarantine path that
cannot be resolved must **not** silently start a fresh empty ledger.

## Call-site tables

For each changed helper: enumerate every consumer, state its disposition on
unverified, and ship a test asserting the file's actual call sites equal the
table — so a new consumer cannot be added bare.

## Verification

Per the parent contract, all four sites get fail-closed + permit + a probe-only
mutant control.

- **Shims** are argv-keyed `PATH` `git` wrappers failing exactly one verb
  (`diff --cached`, `status --porcelain`, `diff --diff-filter=U`,
  `rev-parse --git-dir`), **scoped** so they do not abort the run before the
  probe is reached — `install_failing_add_shim` in
  `tests/test_sync_branch_mode_automerge.sh` shows the scoping technique
  (`ait sync` runs `git add` during auto-commit *before* the pull, so a
  blanket-failing shim never reaches a conflict).
- **Preconditions**, asserted in the test *and* its control — pin identity *and*
  symptom, since "the probe returned empty" has several unrelated causes:
  - A3: unshimmed, the paths really are staged by a second session;
  - A4: the entry really is quarantined **and** the holder verdict really is
    free/dead (both clauses, or the test could pass on the first);
  - A5: the rebase really did stop on a conflict;
  - A10: unshimmed the git-dir resolves **and** the quarantine file is non-empty.
- **Discriminating case:** each fixture is one where the action **would
  otherwise have proceeded**, so the refusal can only be the failed probe.
- **Permit direction:** a deferred group still commits normally on a later run;
  a genuinely settled quarantine entry still releases; a real conflict still
  reaches resolution; a healthy worktree still syncs end-to-end.
- **A10's control must specifically assert that a held quarantine entry
  survives** — pre-fix it vanishes with the relocated file, and that
  disappearance is the defect, not the wedge miss alone.

```bash
bash tests/test_sync.sh
bash tests/test_sync_branch_mode_automerge.sh
bash tests/test_sync_auto_commit_scoping.sh
bash tests/test_sync_deferral_and_quarantine.sh
bash tests/test_no_unscoped_task_commit.sh
shellcheck .aitask-scripts/aitask_sync.sh    # baseline: clean apart from SC1091
```

## Risk

### Code-health risk: medium
- Four independent guards in one 1200-line file on the framework's most-run
  path; a mistake in A5's token handling is a wire-contract change. · severity:
  medium · → mitigation: none needed as a task — the call-site tables and the
  per-site controls are the containment, and A3/A4's dispositions reuse existing
  safe outcomes (`_protect`, `QUARANTINE_HELD`) rather than inventing new ones.

### Goal-achievement risk: medium
- Refusing more often could strand a user: A4 holding a quarantine entry
  forever, or A10 refusing to sync. · severity: medium · → mitigation: none
  needed as a task — the permit-direction tests are the check, and every refusal
  must name its recovery route in the message. If any refusal has no recovery,
  say so rather than shipping a dead end.
