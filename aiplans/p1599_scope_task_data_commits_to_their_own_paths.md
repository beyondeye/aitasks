---
Task: t1599_scope_task_data_commits_to_their_own_paths.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1599 — Scope task-data commits to their own paths

## Context

Framework helpers stage a **whole directory** and then commit the **entire git
index** with no path scoping. Any file another live session has mid-edit in
`aitasks/` / `aiplans/` is swept into a commit whose message names a *different*
task. Provenance is lost (`git log -- <file>` mis-attributes the change, and
`aitask_issue_update.sh`, which finds commits by the `(tNN)` tag, can never
associate it with its real task), half-finished state is committed **and
pushed** to other machines, and the author is never involved.

### Measured, on the live `aitask-data` branch (Jul 1 – Aug 25 2026)

| site | mechanism | swallow rate |
|---|---|---|
| `aitask_pick_own.sh:363` | `task_git add aitasks/` | **83/300 (28%)** |
| `aitask_fold_mark.sh:591,616` | `task_git add aitasks/` | **5/11 (45%)** |
| `aitask_sync.sh:176` | `task_git add aitasks/ aiplans/` | **18/66 (27%)** carry >2 task/plan files |
| `aitask_create.sh` | explicit `add <path>` + bare commit | 2/300 (0.7%) |
| `aitask_archive.sh` | explicit `add <path>` + bare commit | 3/300 (1%) |
| `aitask_update.sh` | explicit `add <path>` + bare commit | 0/6 |

Worst individual cases are `ait board` boardidx reshuffles landing under an
unrelated claim: `c1427200b` (claiming t1405) carried **178** foreign task
files; `833c64d69` (t1383) 171; `f173c53ef` (t1243_3) 164.

**The audit splits the surface into two risk classes.** Directory-wide `add` is
the empirical bug (3 sites). The other **16 unscoped `task_git commit` sites**
are a *latent* TOCTOU race — `add <paths>` followed by a bare `commit` still
writes the whole index, which is exactly how t1207 lost 5 files — but they are
empirically near-clean because they already stage explicit paths. Both are in
scope; the plan is honest about which is which.

### Two corrections to the task description

1. **`aitask_pick_own.sh --sync` does not call `aitask_sync.sh`.** It calls
   `task_sync` (a `pull --rebase` helper in `lib/task_utils.sh`) plus
   `aitask_lock.sh --cleanup`. The sync sweep is therefore **not** on every
   pick's Step 0c as the task states — it fires from `ait sync`
   (`ait:234`), the board TUI (`aitask_board.py:11467`), and the syncer TUI
   (`syncer_app.py:2116`). This lowers its frequency but not its severity.
2. **`aitask_sync.sh` has no `--sync` flag** — only `--batch` and `--help`.

### Established in-repo precedent to follow

Three sites already do this correctly and are the pattern to copy:

- `aitask_attach.sh:196-205` — `_attach_commit()`, with a load-bearing comment
  explaining exactly this bug.
- `aitask_gate_record.sh:81-82`
- `aitask_gate.sh:1025-1032` — also the cleanest "is there anything to do"
  guard: `task_git status --porcelain -- "$file"`.

The form is `task_git add -- <paths>` (needed only so an **untracked** path can
be named — a pathspec cannot match one) followed by
`task_git commit -m <msg> -- <paths>`. With a pathspec and no `-i`, git performs
a partial commit that takes those paths' **worktree** content and ignores the
rest of the shared index entirely. `-m` must precede `--`, or git reads the
message as a path.

**Out of scope:** rewriting the ~106 historical mis-attributed commits. The data
branch is shared and has live sessions on it.

## Approach — decompose into 4 children

The four phases differ sharply in risk, so they get separate plans and reviews.
Child 3 carries all of the liveness/race risk; 1, 2 and 4 are mechanical.

### Child ordering and exclusive script ownership

Each script has exactly **one** owning child. No other child may edit it — this
is what stops the mechanical sweep from colliding with the dedicated fold and
sync work.

| child | owns (exclusively) | depends on |
|---|---|---|
| t1599_1 | `aitask_pick_own.sh` | — |
| t1599_2 | `aitask_fold_mark.sh` | — (`--no-sibling-dep`) |
| t1599_3 | `aitask_sync.sh`, `aitask_lock.sh` | — (`--no-sibling-dep`) |
| t1599_4 | `aitask_create.sh`, `aitask_update.sh`, `aitask_archive.sh`, `aitask_zip_old.sh`, `aitask_issue_import.sh` | **t1599_1, t1599_2, t1599_3** |

Children 1–3 touch disjoint files and may run in parallel, so 2 and 3 are
created with `--no-sibling-dep` rather than inheriting the default previous-sibling
chain. **t1599_4 depends on all three**: its tripwire scans every script, so it
must not land until the three primary sites are scoped and the allowlist of
deliberate index-wide commits is settled — otherwise the guard fires on work that
is already planned. t1599_4 must **not** edit the five scripts owned by 1–3.

### Pre-phase (risk mitigations)

Two confirmed inline mitigations. Each is carried into the named child's plan as
its first step, ahead of that child's own implementation steps.

- **`partial_commit_worktree_semantics`** — *first step of t1599_1.* Add a
  characterization test pinning that `commit -m <msg> -- <paths>` commits the
  **worktree** content of those paths, not the index entry: stage the task file,
  modify it again, claim, and assert which version landed. This runs before any
  scoping edit, so the semantic the other three children inherit is written down
  and asserted rather than assumed.
- **`sync_caller_no_commit_audit`** — *first step of t1599_3.* Before touching
  `auto_commit`, audit `parse_sync_output` (`lib/sync_action_runner.py:87-140`)
  and the three consumers (`ait:234`, `aitask_board.py:11474-11503`,
  `syncer_app.py:2127-2160`) to determine which status token a legitimately
  no-commit run must emit so that none of them classifies it as an error.
  Record the required token in the child's plan before the redesign.

### t1599_1 — Scope the claim commit in `aitask_pick_own.sh`

Highest frequency (every claim), 28% → 0%.

`commit_and_push()` (`aitask_pick_own.sh:360-373`) takes only `task_id`. Thread
the paths in. The only data-branch paths a claim writes are the **task file**
(`resolve_task_file`, already resolved at `:396`) and
`aitasks/metadata/emails.txt` (`EMAILS_FILE`, `:68`, written by `store_email` at
`:232-237`). Lock artifacts live as blobs on the orphan `aitask-locks` branch
and are never in the data index, so they need no path. `.aitask-gates/` is
gitignored and written after the commit.

```bash
commit_and_push() {
    local task_id="$1"; shift
    local paths=( "$@" )
    (( ${#paths[@]} )) || { info "No paths to commit"; task_push; return 0; }

    # `add` is needed only so an untracked path can be named by the pathspec.
    task_git add -- "${paths[@]}" >/dev/null 2>&1 || true

    if [[ -z "$(task_git status --porcelain -- "${paths[@]}" 2>/dev/null)" ]]; then
        info "No changes to commit (task may already be in Implementing status)"
    else
        task_git commit -m "ait: Start work on t${task_id}: set status to Implementing" \
            --quiet -- "${paths[@]}"
    fi
    task_push
}
```

The empty-`paths` guard is load-bearing: `commit --` with no pathspec commits
the whole index, re-creating the bug. Note the no-op guard at `:366` is *also*
index-wide today (`diff --cached --quiet` with no pathspec), so unrelated staged
content currently decides whether the claim commits at all — it must be scoped
in the same edit.

Call site (`:475`) builds the array conditionally — `:396` has `|| true`, so
`task_file` can be empty, and `emails.txt` exists only when an email resolved.

**Test** — `tests/test_pick_own_scoped_commit.sh`. No test anywhere asserts this
commit today (`grep -rn 'Start work on t' tests/` → zero hits). Fixture: clone
`setup_paired_repos` from `tests/test_lock_force.sh:37-91`; seed a bystander
`aitasks/t2_bystander.md` and leave it dirty; claim t1; assert with the
`tests/test_gate_record.sh:83-96` idioms that
`git show --name-status --pretty=format: -M0 HEAD` contains **only** t1's paths
and that the bystander is still ` M` unstaged (the
`tests/test_archive_no_overbroad_add.sh:154-167` assertion shape).
**Negative control:** run the same fixture against the pre-fix
`commit_and_push` and confirm it fails on the bystander assertion.

### t1599_2 — Scope `aitask_fold_mark.sh`, and make the amend fail loudly

45% → 0%. The exact path set is **already computed** at the commit site:
`rollback_paths` (`:567-580`) = primary file + folded files + transitive files +
parents of folded children (the `children_to_implement` edit) + rebound
attachment-meta relpaths. It is used only for rollback today. Reuse it as the
commit pathspec in both `fresh` (`:591-613`) and `amend` (`:616-625`) — no new
derivation logic.

The `amend` path needs a guard. Today it is a bare
`task_git commit --amend --no-edit` against whatever HEAD happens to be, with no
hash, ancestry or authorship check. If that commit already carries foreign
files, `--amend` silently re-attributes them under the fold message and changes
their SHA — and if it was pushed, rewrites published history. Before amending:

```bash
foreign="$(task_git show --name-only --format='' HEAD | grep -v '^$' \
    | grep -vxF -f <(printf '%s\n' "${rollback_paths[@]}") || true)"
[[ -z "$foreign" ]] || die "refusing --commit-mode amend: HEAD ($(task_git rev-parse --short HEAD)) carries paths outside this fold:
$foreign
Re-run with --commit-mode fresh."
```

Also record (do not fix here) two adjacent findings: `amend` has no
`diff --cached --quiet` no-op branch, so an amend with nothing staged still
rewrites the commit and prints `AMENDED`; and `_fold_rollback` (`:583-586`)
restores only `rollback_paths`, so a failed commit that had staged foreign files
left them staged — which scoping makes moot.

**Test** — extend `tests/test_fold_mark.sh`: bystander-not-swept (both modes),
and an amend against a HEAD seeded with a foreign file asserting a non-zero exit
and that HEAD's SHA is **unchanged**.

### t1599_3 — `aitask_sync.sh`: per-task commits + live-lock skip

The risky one; own plan and review. The sweep is intentional, so scoping alone
is not the answer. Replace the single blanket commit (`:165-178`) with:

**1. Parse the dirty set with a NUL-delimited porcelain — never plain lines.**
`git status --porcelain` (no `-z`) renders a rename as `R  <old> -> <new>` on one
line and C-quotes any path containing a space:

```
R  aitasks/t42_some_task.md -> aitasks/archived/t42_some_task.md
 M "aitasks/t43_with space.md"
```

A naive `cut -c4-` therefore hands the grouper a single string containing **two**
paths, which can match two owners at once or the wrong one, and quoted paths do
not exist on disk under that name. Archive moves are exactly this shape, so it is
not a corner case. Use `task_git status --porcelain -z` and parse NUL-delimited:

```
R  aitasks/archived/t42_some_task.md\0aitasks/t42_some_task.md\0 M aitasks/t43_with space.md\0
```

Note the ordering trap: with `-z` a rename emits **`<new>` first, then `<orig>`** —
the reverse of the arrow display — and quoting is gone. Pin this in a test.

**2. Group by owning task id.** `aitasks/t<N>_*.md`, `aitasks/t<P>/t<P>_<C>_*.md`,
`aitasks/archived/…`, `aiplans/p<N>_*.md`, `aiplans/p<P>/p<P>_<C>_*.md`.
For a rename, resolve the owner of **both** paths:
- same owner (the archive case) → group normally;
- **different owners → skip and report as an ambiguous cross-task rename.**
  Never guess an owner for an entry that legitimately names two.

**3. Never auto-commit an ownerless path.** Anything with no derivable task id —
`aitasks/metadata/*`, artifacts, stray files — is **skipped and reported**, not
swept into a residual commit. This is the documented failure mode:
`aitasks/metadata/stats_config.json` has four commits in its whole history and
**three are swallows** (`da9dfeb89`, `c4445b4eb`, `442c65179`); a residual
auto-commit would leave that exact case unfixed, still committing and pushing an
in-flight edit without its author. Those files stay dirty until the session that
changed them commits them — which is now safe, because after t1599_1 the claim
path no longer sweeps them either. An explicit `--commit-unowned` opt-in restores
the old behaviour for anyone who wants it.

**4. Skip any file whose owning task is held by a *live* lock.** Reuse the
canonical seam — `lock_holder_liveness()` / `is_lock_holder_alive()` in
`lib/pid_anchor.sh` (the t1466 gate) — do not reimplement liveness. Fetch the
lock branch **once** and enumerate rather than one `aitask_lock.sh --check` (and
one `git fetch`) per task: extend `aitask_lock.sh --list` with a `--batch`
machine-readable form emitting `LOCK:<id>|<email>|<host>|<pid>|<starttime>|<kind>`.
Extending the existing helper is preferred over forking its scan logic; the human
`--list` output is left unchanged.

**5. Fail safe when liveness is undecidable — do not fall back to sweeping.**
Per-verdict: `dead` → commit (the recovery case); `alive` → skip;
`unknown` → **skip** (treat as live).

The lock-branch-unreadable case needs care, because `check_lock` / `list_locks`
currently fail **open** — they return "not locked" for a genuinely absent branch,
a network failure, and an empty branch alike. Committing everything in that state
would recreate the precise cross-session swallow this task exists to stop: an
outage can easily coincide with a live editor. So `--batch` must return three
**distinct** statuses, and each routes differently:

| status | meaning | action |
|---|---|---|
| `LOCKS_NONE` | branch readable, no locks held | commit all owned groups |
| `LOCKS_UNINITIALIZED` | lock branch does not exist — locking was never set up, so no task in this repo *can* be locked | commit all owned groups |
| `LOCKS_UNAVAILABLE` | branch exists but could not be read (fetch/network/ls-tree failure) | **skip every task-owned file and report**; commit nothing |

`LOCKS_UNAVAILABLE` is "busy vs impossible" — an unreadable lock branch is not
evidence of no locks. The availability-over-safety choice is made **explicitly**
by the operator via `--assume-unlocked`, never silently by an outage.

A useful narrowing: `main()` runs `check_remote` (`:154-162`) at step 2, which
exits 0 with `NO_REMOTE` **before** `auto_commit` at step 3 — so `auto_commit`
only ever runs when a remote exists, and the no-remote case never reaches this
decision at all.

**7. Protect the rebase — a skipped file must not break the sync.** This is the
invariant `auto_commit` actually exists to maintain: it clears the worktree so
that step 7's `pull --rebase` can run. Leaving files dirty breaks it. Verified:

```
$ git status --porcelain   ->   M aitasks/t2_b.md
$ git pull --rebase
error: cannot pull with rebase: You have unstaged changes.
error: Please commit or stash them.            rc=128
```

`do_pull_rebase`'s non-conflict branch then emits `ERROR:pull_rebase_failed` and
`return 1`, and `main()` exits 1 (`:504`) — so one correctly-protected file would
block fetch/pull/push for `ait sync` and for both TUIs. Unacceptable.

**Stashing is not the answer.** `git stash` / `rebase.autoStash` would move
another live session's in-flight edits into a stash they do not know about — the
exact hazard recorded from t635_33, where a concurrent stash+reset swept a
session's unstaged work. Never stash a file being protected *because* another
session owns it.

So: **protected-dirty early exit.** After grouping, if any file is protected
(live lock / unknown liveness / locks unavailable / ownerless / ambiguous
rename), then:

- commit every eligible group as normal, and always run the read-only fetch;
- if `remote_ahead == 0`, continue normally — `do_push` does not need a clean
  tree, so local commits still publish;
- if `remote_ahead > 0`, **skip `do_pull_rebase` entirely**, emit a new
  caller-recognized status naming the count and reason, and **exit 0** — a
  deferral, not an error. Report which task/session holds each protected file.

Deferring the rebase here is also the right call on its own merits: rebasing the
shared data branch underneath a live session's uncommitted work is precisely the
clobber hazard that argues for leaving reconciliation to the owning session.
The cost is bounded and self-clearing — the deferral lasts only until that
session commits its own work, which is now safe because after t1599_1 the claim
path no longer sweeps it either.

The new status token must be added to `parse_sync_output`
(`lib/sync_action_runner.py:87-140`) and classified as a benign outcome by all
three consumers — folded into the `sync_caller_no_commit_audit` pre-phase, whose
scope covers both the no-commit and the deferred-rebase tokens.

One staging detail follows from this: only ever `add` an **untracked** path, and
only immediately before its own group's commit. A path left staged by a failed
`add`/commit would block the rebase just as an unstaged one does.

**7b. Carry the protected-dirty state into `do_push` — the step-7 guard is not
enough.** `remote_ahead` is computed once, from the step-5 fetch. On a branch
several sessions push to in parallel, the remote can advance *after* that fetch,
so a run that correctly saw `remote_ahead == 0` still reaches `do_push` and gets
its push rejected. Today's retry then does exactly the wrong thing
(`aitask_sync.sh:456-470`):

```bash
elif [[ $push_exit -ne 0 ]]; then
    _git_with_timeout fetch origin 2>/dev/null || true
    task_git pull --rebase --quiet 2>/dev/null || true   # <-- failure SWALLOWED
    _git_with_timeout push origin 2>/dev/null || retry_exit=$?
    if [[ $retry_exit -ne 0 ]]; then batch_out "ERROR:push_failed"; return 1; fi
```

With protected files present the `pull --rebase` refuses (rc 128), `|| true`
swallows it, the still-un-rebased push is rejected again, and the run reports
`ERROR:push_failed` — bypassing the protection entirely and blaming the push for
a failure the protected files caused. This is an ordinary shared-branch race, not
an edge case.

Fix: hold the protected-dirty state (count + reasons + holders) in a script-scope
variable set during grouping, and consult it in `do_push`:

- **protected-dirty set, push rejected** → do **not** `pull --rebase`, do **not**
  retry the push. Emit the same deferred token and return the deferred outcome
  (exit 0). The local commits stay local and publish on a later run.
- **protected-dirty unset** → today's fetch + rebase + retry, unchanged.

While here, stop the retry path swallowing a genuine rebase failure: check the
rebase's exit status and route on it rather than blind-retrying a push that
cannot succeed. Blind-retrying is what turns a diagnosable cause into
`ERROR:push_failed`.

**8. Report** the skipped files with their reason (live lock / unknown liveness /
locks unavailable / ownerless / ambiguous rename).

Preserve the existing contract: `auto_commit` is best-effort today
(`2>/dev/null || true` on both lines, always returns 0) and `run_sync_batch`
never reads the exit status — only stdout. The new grouping must not turn a
commit failure into a script failure, and must keep emitting a first-line status
token `parse_sync_output` understands.

**Tests:** live lock → file skipped and left dirty; stale/dead lock → file
committed; `unknown` liveness → skipped; mixed locked+unlocked → correct
partition in one run; nothing eligible → clean no-op, no commit created
(`rev-list --count` unchanged, the `tests/test_gate_record.sh:100-107` idiom);
**rename/move grouping**, including a same-owner archive move and an ambiguous
cross-task rename; ownerless file → skipped and reported, not committed;
`LOCKS_UNAVAILABLE` → nothing committed; `LOCKS_UNINITIALIZED` → committed;
`--assume-unlocked` → committed.

**The rebase-protection test the concern demands:** seed a remote-ahead branch,
leave one live-locked file dirty, run sync, and assert it exits **0** with the
deferred token — not `ERROR:pull_rebase_failed` — and that fetch still happened.
Pair it with a control where nothing is protected, proving the rebase still runs.

**Remote-advance-after-fetch test (the push-retry race).** Inject it through a
documented git seam rather than a production test hook: install a `pre-push` hook
in the fixture's data repo that, on its first invocation, pushes a commit from a
sibling clone to the same remote. Our push is then genuinely rejected exactly
once, deterministically entering `do_push`'s retry path. With a protected dirty
file present, assert the run exits **0** with the deferred token and **not**
`ERROR:push_failed`; with none, assert the existing rebase+retry still succeeds.

### t1599_4 — Sweep the 16 latent unscoped commit sites + tripwire

Mechanical. `aitask_create.sh` (7), `aitask_update.sh` (2),
`aitask_archive.sh` (3), `aitask_zip_old.sh` (1), `aitask_issue_import.sh` (1),
plus the fold/sync/pick_own sites closed by children 1–3. Each already stages an
explicit path list; convert `add <paths>` + bare `commit` to
`commit -m <msg> -- <paths>`.

Two need care rather than the mechanical edit:
- `aitask_zip_old.sh:539` uses `add -u "$TASK_ARCHIVED_DIR/"` — genuinely
  directory-scoped by design (archive bundling); scope the commit to those same
  directory pathspecs, not to a file list.
- `aitask_issue_import.sh:792` is a `commit --amend`; it needs the same
  foreign-path guard as t1599_2.

**Tripwire** — `tests/test_no_unscoped_task_commit.sh`, in the spirit of
`tests/test_no_raw_tmux.sh`: fail if a `task_git commit` line carries no `--`
pathspec, with a documented allowlist for any deliberate index-wide commit.

**What this child does NOT buy:** it closes a latent race, not an observed
defect — these sites measured 0–1%. The tripwire is a grep, so it catches the
common single-line shape and will not see a commit assembled across lines or
through a variable; it is a regression tripwire, not a proof.

## Verification

- Per-child bash tests above; each new test must be shown to **fail against the
  pre-fix script** (a real negative control, per the task's requirement).
- `shellcheck .aitask-scripts/aitask_*.sh`
- Re-run the history scan; claim commits made after the fix must show a **0%**
  foreign-path rate:

```bash
tot=0; bad=0
while IFS=$'\t' read -r sha subj; do
  id=$(printf '%s' "$subj" | sed -n 's/^ait: Start work on t\([0-9_]*\):.*/\1/p')
  [ -n "$id" ] || continue
  tot=$((tot+1))
  n=$(git -C .aitask-data show --name-only --format='' "$sha" | grep -v '^$' \
      | grep -v '^aitasks/metadata/emails.txt$' \
      | grep -vcE "(^|/)t${id}(_|\.md$)" || true)
  [ "$n" -gt 0 ] && bad=$((bad+1))
done < <(git -C .aitask-data log --format='%H%x09%s' -n 400 --grep='^ait: Start work on t')
echo "$bad/$tot claim commits carry a foreign path"
```

Baseline today: **106/400**. Note the scan must run against `.aitask-data` —
`main` still carries 81 pre-migration claim commits from Feb 2026 that are not
current behaviour.

- Post-implementation cleanup, archival and merge follow **Step 9
  (Post-Implementation)** of the shared task workflow.

## Risk

### Code-health risk: medium
- The sync redesign (t1599_3) replaces a 14-line best-effort sweep with owner-grouping plus liveness classification, adding real logic to a path that runs from three TUIs and must never fail the caller. · severity: medium · → mitigation: t1599_3 regression tests (live / stale / mixed / nothing-eligible)
- `commit -- <pathspec>` performs a **partial** commit that takes worktree content and ignores the index for those paths; a path staged-but-since-modified commits its worktree version, a subtle behaviour change from today's index-wide commit. · severity: medium · → mitigation: inline pre-phase partial_commit_worktree_semantics
- An empty path array turns `commit --` back into a whole-index commit, silently re-creating the exact bug being fixed. · severity: high · → mitigation: t1599_1 empty-pathspec guard + its regression test
- Extending `aitask_lock.sh --list` with a `--batch` form adds a second output contract to a script whose current output is human-prose. · severity: low · → mitigation: t1599_3 keeps the human `--list` output unchanged and adds `--batch` alongside it
- The t1599_4 tripwire is grep-shaped and cannot see a multi-line or variable-assembled commit, so it may read as stronger enforcement than it is. · severity: low · → mitigation: documented as a tripwire, not a proof, in t1599_4

### Goal-achievement risk: medium
- Liveness is a tri-state (`alive`/`dead`/`unknown`) and `check_lock` fails **open** — it reports "not locked" for an absent branch, a network failure and an empty branch alike. Sweeping in that state would recreate the exact cross-session swallow this task exists to stop, since an outage can coincide with a live editor. · severity: high · → mitigation: t1599_3 splits the status into LOCKS_NONE / LOCKS_UNINITIALIZED / LOCKS_UNAVAILABLE; UNAVAILABLE commits nothing, and availability-over-safety is an explicit `--assume-unlocked` operator choice
- A lock can be released between the liveness check and the commit (TOCTOU on the skip decision itself), so the skip is advisory, not a guarantee. · severity: medium · → mitigation: accepted: the skip is advisory by design; the owning session still commits its own work
- Ownerless paths (`aitasks/metadata/*`, artifacts) have no natural attribution, and auto-committing them is precisely the documented `stats_config.json` failure mode — an in-flight edit committed and pushed without its author. · severity: high · → mitigation: t1599_3 never auto-commits an ownerless path; it skips and reports, with `--commit-unowned` as an explicit opt-in
- Skipping a file leaves the worktree dirty, which breaks the invariant `auto_commit` exists to maintain: `git pull --rebase` refuses with unstaged changes (verified, rc=128), so `do_pull_rebase` would emit `ERROR:pull_rebase_failed` and `main()` would exit 1 — one protected file blocking fetch/pull/push for the CLI and both TUIs. · severity: high · → mitigation: t1599_3 protected-dirty early exit (skip the rebase, emit a deferred token, exit 0) + a remote-ahead-while-skipped test; stashing is explicitly rejected
- `remote_ahead` is sampled once from the step-5 fetch, but `do_push`'s rejected-push retry runs its own `pull --rebase` with the failure swallowed by `|| true`; a remote advance after that fetch therefore bypasses the step-7 protection and surfaces a misleading `ERROR:push_failed`. · severity: high · → mitigation: t1599_3 carries protected-dirty state into `do_push` (defer instead of rebase+retry) and stops the retry path swallowing the rebase status; pinned by a pre-push-hook remote-advance test
- A long-lived protected file defers the rebase for as long as the owning session holds it, so the data branch stops auto-reconciling in the meantime. · severity: medium · → mitigation: bounded and self-clearing — the deferral ends when the owning session commits, which t1599_1 makes safe; the deferred status names the holder so it is visible rather than silent
- A sync that finds only live-locked changes now legitimately produces **no commit**, which callers assuming "sync always commits" may read as a failure. · severity: medium · → mitigation: inline pre-phase sync_caller_no_commit_audit
- `git status --porcelain` without `-z` renders a rename as one line naming **two** paths and C-quotes paths containing spaces, so a naive parser can assign an archive move to two owners or to the wrong one. · severity: medium · → mitigation: t1599_3 parses `--porcelain -z` (rename emits `<new>\0<orig>`) and skips ambiguous cross-task renames rather than guessing; pinned by a rename/move grouping test
- Four children editing overlapping scripts could produce conflicting edits, and the t1599_4 tripwire could fire before the deliberate index-wide exceptions are settled. · severity: medium · → mitigation: the exclusive script-ownership table plus t1599_4 depending on t1599_1/2/3
- The 0%-foreign-rate verification is a lagging indicator: it only becomes meaningful after enough new claims accumulate on the data branch. · severity: low · → mitigation: verify_zero_foreign_rate_after_soak

### Planned mitigations
- timing: pre-phase | name: partial_commit_worktree_semantics | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: partial commit takes worktree content, not the index entry | desc: Characterization test pinning which version of a staged-then-modified path a path-scoped commit captures.
- timing: pre-phase | name: sync_caller_no_commit_audit | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: a legitimately no-commit sync run, and a deferred rebase, may be misread as failure | desc: Audit parse_sync_output and the three sync consumers to fix the status tokens a no-commit run and a protected-dirty rebase deferral must emit, before redesigning auto_commit.
- timing: after | name: verify_zero_foreign_rate_after_soak | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the 0%-foreign-rate check is a lagging indicator | desc: Re-run the claim-commit history scan once ~50 new claims have landed post-fix and confirm the production foreign-path rate is 0%.
