---
Task: t1747_sweep_failopen_git_probes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1747 — Sweep fail-open git probes at authorization sites

## Context

A `|| true`-suppressed git probe collapses "the probe failed" into "the answer
is empty" — and empty is almost always the *permissive* answer: "no conflicts",
"nothing foreign", "nothing staged", "nothing dirty". Two instances have already
been closed as fail-open authorization bugs (`aitask_issue_import.sh`, t1599_4;
and `aitask_fold_mark.sh::_fold_amend_guard`, t1733, where a merge HEAD was
measurably rewritten). t1733's `## Risk` section recorded that the class was
still alive at more destructive sites and spawned this task.

The rule is the one `lib/task_utils.sh::task_git_commit_scoped:473` already
states, and which `aitask_metadata_commit.sh:174`, `aitask_gate.sh:1035`,
`aitask_issue_import.sh:650` and `aitask_fold_mark.sh:915` already follow:

> **Capture the probe's exit status separately — empty output only means
> "nothing" when `rc == 0`.**

What a failed probe should then *do* is site-specific. The fail-safe direction
is whichever branch is not destructive: the amend guards **refuse**;
`task_git_commit_scoped` **commits anyway with a warning**, because there
committing is the safe direction.

### The audit found 13 authorizing sites, not 2

The task body names two candidates. A full sweep of `.aitask-scripts/` found
**thirteen** probes whose answer gates a destructive or authorizing action, across
six files — plus a large informational set that is correctly out of scope. Every
site in the table below was re-read and confirmed first-hand.

### Stale references in the task body

`aitask_sync.sh::_rebase_advance` **no longer exists**: commit `66da94134`
(t1727) extracted it to `lib/task_automerge.sh::ait_automerge_advance:203`, and
it is now reachable from **two** drivers (`ait sync` *and* every pick/push via
`lib/task_utils.sh::_task_pull_rebase`) rather than one — the blast radius grew.
The lines the task names as `aitask_sync.sh:1008`/`:1025` are today
`rebase --abort … || true` recovery calls, which are best-effort cleanup, not
probes. All line numbers below are the current tree.

---

## Group A — authorizing / destructive, fail-open

| # | site | probe answers | gates | on probe failure |
|---|---|---|---|---|
| A1 | `lib/task_automerge.sh:203` | "any unresolved conflict paths?" | **`git rebase --skip`** | reads "empty patch" ⇒ **discards the replayed commit** |
| A2 | `lib/task_automerge.sh:212` | same, `_ait_automerge_conflicted_now` | loop entry ⇒ compounds into A1; post-advance ⇒ `return 2` ⇒ abort | entry use is fail-open *into A1*; post-advance use is already fail-closed |
| A3 | `aitask_sync.sh:772` | "has another session staged these paths?" | `add` / `commit -o` / `reset` in `_commit_group` | reads "nobody staged" ⇒ **replaces another session's index entry** — the exact harm its own comment names |
| A4 | `aitask_sync.sh:503` | "is this quarantined path settled?" | **releasing a publication quarantine** | reads "clean/settled" ⇒ **pushes a commit deliberately withheld**. Its comment argues at length that a clean worktree is not settlement — yet an *unreadable* one currently reads as clean |
| A5 | `aitask_sync.sh:919` | "did `pull --rebase` stop on a conflict?" | conflict resolution vs. **unconditional `rebase --abort`** | reads "not a conflict" ⇒ aborts a real in-progress resolution (recoverable via `ORIG_HEAD`) |
| A6 | `aitask_fold_mark.sh:961` | "is HEAD already published upstream?" | **`commit --amend`** (history rewrite) | two holes: `\|\| true` conflates "no upstream" with "rev-parse failed"; and `merge-base --is-ancestor` returns **≥2 on error**, treated as "not published" ⇒ amend authorized |
| A7 | `aitask_issue_import.sh:686` | identical to A6 | **`commit --amend`** | identical two holes |
| A8 | `aitask_merge_task.sh:82-83` | "unmerged paths? tree dirty?" | force-release lock deletion; **post-`reset --hard` verification** | `_tree_dirty_tracked` prints `0` both when clean and when `git status` failed ⇒ reports `FORCE_RELEASED` on an unverified tree |
| A8b | `aitask_merge_task.sh:81` `_merge_head_present` | "is a merge in progress?" | **the force-release remedy selector** (`:406`) and the **post-`merge --abort` verification** (`:411`) | `[[ -f "$(git rev-parse --git-dir)/MERGE_HEAD" ]]` — a failed `rev-parse` yields empty, so the test degrades to `[[ -f "/MERGE_HEAD" ]]` ⇒ **"no merge in progress"**. Consequences at both consumers, below |
| A9 | `aitask_setup.sh:3591-3594` | "which framework files are dirty?" | the **baseline subtracted** so setup does not sweep foreign work | empty baseline ⇒ **another session's uncommitted work is committed under `ait: Add aitask framework`** |
| A9b | `aitask_setup.sh:3647, :3763` | "is `.aitask-scripts/VERSION` tracked?" | bootstrap ⇒ commit-**all** | `&>/dev/null` conflates untracked (rc 1) with git error (rc 128) ⇒ same sweep. Measured in a scratch repo: the two rcs *are* separable |
| A10 | `aitask_sync.sh:301` | "which git-dir owns the data worktree?" | `_worktree_wedged` early refusal; quarantine file location | fabricated `.git` ⇒ "not wedged" ⇒ sync proceeds; **and relocates the quarantine file, losing every held entry** |
| A12 | `aitask_lock.sh:195` | "does a lock already exist?" | acquiring a task lock **over another session's** | failed `ls-tree` ⇒ no output ⇒ `grep -q` false ⇒ **the entire lock-exists block at `:195-276` is skipped**, and with it *every* liveness gate: `LOCK_LIVE_HOLDER`, `LOCK_UNVERIFIABLE_HOLDER` and `LOCK_RECLAIM`. That is a silent reprise of the t1466 defect those gates exist to prevent — two live sessions owning one task |

`A11` (`task_git_commit_scoped:477`) is **correct as written** — it already
separates rc from empty and deliberately resolves the unknown toward
*committing*, which is that site's safe direction. It is the reference pattern,
not a defect.

## Deliberately left alone (recorded per the task's scope discipline)

| site | why it stays |
|---|---|
| `aitask_sync.sh:1004,:1009,:1015` `rebase --abort … \|\| true` | best-effort *recovery* on an already-failing path, not a probe gating anything |
| `aitask_setup.sh:3804` post-commit `still_untracked` | feeds a `warn` only |
| `aitask_remote_drift_check.sh` | pure reporter, exits 0; `:182`/`:191` already fail **closed** to `FETCH_FAILED`. `:219` is a soft spot (a failed diff reads as `NO_OVERLAP`) but advisory only — noted, not fixed |
| `aitask_change_surface.sh` | display-only; written best-effort by `aitask_pick_own.sh:681`, read by the docs-updated gate skill |
| `aitask_revert_analyze.sh` | read-only analyzer. `:172`'s failure direction is *under*-destructive ("no commits found" ⇒ nothing reverted) |
| `lib/task_utils.sh:718,724,1242-1252` | documented always-return-0 reporting probes; empty is a *declared* "undeterminable" value the warning text handles |
| `lib/data_symlinks.sh:104`, `lib/txn_snapshot.sh:112` | already exemplary — round-trip verification / explicit `die`. Cite as models |
| `aitask_merge_task.sh:84` `_head_branch` | empty reads as detached ⇒ `RECOVERY_FAILED`. Already fail-closed |

**Group C — swallowed *mutation* failures.** Not probes, but the same blast
radius and worth naming so a later reader does not think the sweep missed them:
`aitask_setup.sh:1871` (failed `git rm` swallowed, then an unconditional
`rm -rf`), `aitask_archive.sh:413,419` (a failed `rm` drops the path from the
commit's pathspec), `aitask_zip_old.sh:537-539`, and the `add … || true`
immediately before both `commit --amend` sites. Recorded in the doc as future
work; **not** in this task's scope, which is probes.

---

## Approach: decompose

Each fix needs its own negative control against a probe-only mutant plus
asserted fixture preconditions — t1733 needed six tests for **one** site. Thirteen
sites across six files is not one reviewable change, and the files are
independent, so this becomes a parent with children.

**One deviation from the option as I put it to you:** I proposed the parent
itself would own the audit record. A decomposed parent reverts to `Ready` and is
never implemented, so a parent-owned deliverable would never land. The audit doc
is therefore **child 1** instead, ordered first so the code children can point
at it. Nothing else about the split changes.

### Coverage map — every Group A row is assigned

The parent's goal is "every authorizing probe". That claim is only true if the
children partition the table, so here it is explicitly; t1747_1's doc carries
the same map, and a Group A row with no child is a defect in this plan.

| Group A row | child |
|---|---|
| A1, A2 | t1747_2 |
| A3, A4, A5, A10 | t1747_3 |
| A9, A9b | t1747_4 |
| A6, A7 | t1747_5 |
| A8, A8b, A12 | t1747_6 |
| A11 | none — correct as written (see above), not a defect |

### Children

Children auto-depend on siblings, so they run in this order.

**t1747_1 — `aidocs/framework/failopen_git_probes.md`** (documentation)
The durable audit record: the rule, the canonical fix shape with its four
existing call sites, the Group A table above, the negative-space table, and
Group C as named future work. Cross-referenced from
`aidocs/framework/shell_conventions.md` **in a later, separate commit** — that
file currently carries ~24 uncommitted lines from another live session, and
committing it now would sweep their work in. Code comments in children 2-6
**point at this doc rather than restating the rule**, so the N-copies drift this
task is fixing is not recreated. Explicitly *not* a regex tripwire over
`|| true`: the legitimate uses vastly outnumber the defects (Group B is an order
of magnitude larger than Group A), so a scanner would fail on correct code and
its false positives would break unrelated work.

**t1747_2 — `lib/task_automerge.sh`: A1 + A2** (the `rebase --skip` authorization)
Highest severity: the fail-open outcome is a discarded commit, on the hottest
path in the framework. Fix shape:

```bash
    local unresolved="" u_rc=0
    unresolved="$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null)" || u_rc=$?
    if (( u_rc == 0 )) && [[ -z "$unresolved" ]] && _ait_data_git rebase --skip &>/dev/null; then
        return 0
    fi
    return 1
```

`return 1` is verified safe at all three call sites — `ait_automerge_rebase_loop:272`
⇒ `return 2` ⇒ abort; `aitask_sync.sh:1002` ⇒ warn + abort; `task_utils.sh:1216`
⇒ rc 1 and 2 both fall through to the verified abort. Every route ends in an
abort that restores the worktree and keeps local commits.

**t1747_3 — `aitask_sync.sh`: A3, A4, A5, A10** (four guards, one file; effort high)
The shared-index staged guard, the quarantine release clause, the
conflict-vs-other-error classifier, and `_sync_gitdir`'s silent `.git` fallback.
Grouped because they share a file and a test harness; each still gets its own
control. A4 and A10 both end in publishing something the framework withheld, so
they are the pair to fix together. A10 needs the full call-site treatment:
`_sync_gitdir` has two direct consumers (`_worktree_wedged:343`,
`_quarantine_path:306`) and `_quarantine_path` fans out to four more, so an
unresolvable git-dir must be refused at the helper rather than papered over with
the `.git` default that silently relocates the quarantine file.

**t1747_4 — `aitask_setup.sh`: A9 + A9b** (the dirty baseline)
Give `_ait_list_framework_changes` a real rc (the *trailing* `|| true` on the
`grep -Ev` pipeline is load-bearing and stays — `grep -Ev` exits 1 on a
legitimately empty result); set `AIT_SETUP_BASELINE_UNVERIFIED=1` rather than
arming an empty baseline; make both commit functions refuse and name the manual
recovery. Extract one `_ait_framework_version_tracked` helper returning
0/1/2 for the duplicated VERSION probe. Note `AIT_SETUP_BASELINE_ARMED` stays
`1` today even when all three probes fail, so the "baseline not armed" warning
never fires — that is part of the defect.

**t1747_5 — `aitask_fold_mark.sh` + `aitask_issue_import.sh`: A6 + A7**
The published-history amend guards. Identical shape in both files, and the fixed
pattern already sits 40 lines above each one (`:915` / `:650`) — this is a
copy-the-sibling change. Must also treat `merge-base --is-ancestor` rc **≥2** as
"refuse", which the current `if` conflates with "not published". The existing
"ACCEPTED RESIDUAL" comment covers only *staleness* of the tracking ref, not
probe failure, so this is an un-audited hole rather than an accepted one — the
comment needs amending to say which residual actually remains.

**t1747_6 — lock & reservation authorization: A8 + A8b + A12**
Two files, one theme: probes that decide whether to **take or release a lock**.

*`aitask_merge_task.sh` — A8 + A8b: a tri-state helper API and **every**
consumer.* These are not three-call-site fixes. The two helpers at `:81-83` have
**7 and 8 consumers**, spread across four commands — pre-merge admission
(`:168`, `:171`), post-merge verdict rendering (`:213`), normal abort and
reservation release (`:251`-`:266`), force-release (`:406`-`:424`), and dry-run
remedy guidance (`:466`-`:478`). Fixing only force-release would leave the other
paths reading an unreadable repository as clean / no-merge.

**The sentinel-value trap, measured.** The obvious fix — return a magic value
from these helpers — is wrong in both spellings, because `_tree_dirty_tracked`'s
value is consumed by `[[ "$(…)" -gt 0 ]]`, an *arithmetic* context:

| sentinel | what `[[ "$s" -gt 0 ]]` actually does |
|---|---|
| `"unverified"` | bash resolves it as a **variable name**; under this script's `set -u` (`:25`) it **aborts the script** — mid-force-release, possibly after the lock dir was removed |
| `-1` or `""` | evaluates false ⇒ silently reads as **clean** — a brand-new fail-open |

So the unverified state must travel on the **exit status**, never on stdout:

```bash
# 0 = verified (count on stdout); 2 = unverified (stdout empty).
_tree_dirty_tracked() {
    local out rc=0
    out="$(git status --porcelain -uno 2>/dev/null)" || rc=$?
    (( rc == 0 )) || return 2
    printf '%s' "$(printf '%s' "$out" | grep -c '.' || true)"
}
# 0 = merge in progress; 1 = none; 2 = unverified.
_merge_head_present() {
    local gd rc=0
    gd="$(git rev-parse --git-dir 2>/dev/null)" || rc=$?
    { (( rc == 0 )) && [[ -n "$gd" ]]; } || return 2
    [[ -f "$gd/MERGE_HEAD" ]]
}
```

Both helper bodies above were run in a scratch repo, with and without a
`PATH` shim failing `status --porcelain` / `rev-parse --git-dir`: they return
`rc 0` with the right value when the probe works, `rc 2` with empty stdout when
it fails, and never trip `set -e`.

**Every `if _merge_head_present; then` must be rewritten.** A bare `if` treats
rc 2 as false — i.e. re-creates the exact fail-open — so the refactor is only
complete when no call site consumes these helpers bare. `_unmerged_paths`
(`:82`) gets the same treatment; `_head_branch` (`:84`) stays as-is, since empty
already reads as detached ⇒ refuse, which is fail-closed.

| consumer | today's fail-open consequence | disposition on unverified |
|---|---|---|
| `:168` `_merge_head_present` — pre-merge admission | admits a merge onto a tree with stale merge residue | `PREFLIGHT_UNVERIFIED:merge_state`, **release** (pre-merge refusals release, per the file's own contract at `:188`) |
| `:171` `_tree_dirty_tracked` — pre-merge admission | admits a merge onto a dirty tree | `PREFLIGHT_UNVERIFIED:tree_state`, release |
| `:213` `_unmerged_paths` — verdict rendering | a real conflict is reported as `MERGE_FAILED`, sending the caller down the wrong recovery | distinct `MERGE_FAILED:…:conflict_state_unverified`; reservation is retained either way, so this one is honesty, not safety |
| `:251` `_merge_head_present` — abort branch selection | skips `merge --abort` on a real mid-merge tree, then releases via `RELEASED_NO_MERGE` | `ABORT_UNSAFE:merge_state_unverified`, **do not release** |
| `:254-255` post-abort verification | `ABORTED` + release over a tree that may still hold `MERGE_HEAD` | `ABORT_FAILED:state unverified` |
| `:260,:263,:266` residue checks | releases the reservation over unread residue | `ABORT_UNSAFE:<probe>_unverified`, do not release |
| `:406` force-release remedy selector | a mid-merge tree falls to the `elif` at `:414`: with `--abort-merge` it is refused as `WRONG_REMEDY:no_merge_head` (**blocking the correct remedy**); with `--reset-hard` it runs `git reset --hard HEAD` **over a merge in progress** — the more destructive remedy, chosen because the probe could not be read | `RECOVERY_FAILED:merge state unverified` before any remedy runs |
| `:411`, `:424` post-remedy verification | `FORCE_RELEASED` over an unverified tree | `RECOVERY_FAILED:<tree\|merge> state unverified` |
| `:466-478` dry-run guidance | prints a **wrong remedy flag** and a copy-paste command line carrying it | print `residue: UNVERIFIED — cannot determine remedy` and emit **no** remedy flag in the copy-paste line; never hand the user a destructive flag chosen from an unread probe |

**Making the coverage claim executable.** The child's plan carries a call-site
table for the three helpers, and a test asserts that the set of call sites in
`aitask_merge_task.sh` equals that table — so a ninth consumer cannot be added
bare. Scope is deliberately one file and three known function names, not a
tree-wide search for intent.

Because this grew well past its original size, child 6 is implemented in two
named phases — **6a** the `aitask_merge_task.sh` tri-state refactor, **6b** the
`aitask_lock.sh` probe — and its effort is `high`, not `medium`. Keeping A12
here follows your earlier direction; if 6a's diff proves unwieldy in
implementation, splitting 6b into its own sibling is a clean cut, since the two
share no file and no test suite.

*`aitask_lock.sh` — A12.* `git ls-tree "$current_tree_hash" -- "$lock_file" | grep -q`
decides whether a lock exists. A failed `ls-tree` produces no output, `grep -q`
is false, and **the whole `:195-276` block is skipped** — every liveness gate
with it. Fix: capture the `ls-tree` rc; a non-zero rc is **unverified** ⇒
`die_code` with a distinct message telling the user the lock state could not be
read, never "no lock, acquiring". Partial existing mitigation, stated so the
child does not over-claim: `parent_hash` / `current_tree_hash` at `:189-190` are
**un**suppressed under `set -euo pipefail`, so an unreachable ref already kills
the script before the probe. The residual is a resolvable tree whose `ls-tree`
nonetheless fails — narrower, but its consequence is a total mutex bypass.

**Verification for this child specifically.** Each of the three sites gets a
probe-only mutant control and a permit test, driven through argv-keyed `PATH`
`git` shims that fail exactly one verb:

| command under test | shim fails | fail-closed assertion | permit assertion |
|---|---|---|---|
| `begin` (`:168`, `:171`) | `rev-parse --git-dir` / `status -uno` | `PREFLIGHT_UNVERIFIED:*`, and the reservation is **released** (not stranded) | a clean tree on an existing branch still reaches `MERGE_OK` |
| `begin` verdict (`:213`) | `diff --diff-filter=U` | verdict names the unverified conflict state; reservation **retained** | a real conflict still reports `MERGE_CONFLICT:<files>` |
| `abort` (`:251`-`:266`) | each of the three helpers, one at a time | `ABORT_UNSAFE:*_unverified` / `ABORT_FAILED`, and the lock dir is **still present** | a real `MERGE_HEAD` still aborts and releases (`ABORTED`); a clean tree still reports `RELEASED_NO_MERGE` |
| `force-release` (`:406`, `:411`, `:424`) | `rev-parse --git-dir` / `status -uno`, **each branch separately** — `:406` and `:411` fail differently | `RECOVERY_FAILED:*`, lock dir **still present**, and **no `reset --hard` ran** | a real `MERGE_HEAD` still selects `--abort-merge`; a real dirty-no-merge tree still selects `--reset-hard` and reports `FORCE_RELEASED` |
| `force-release --dry-run` (`:466`-`:478`) | `rev-parse --git-dir` | prints `UNVERIFIED`, and the copy-paste line carries **no** remedy flag | a real `MERGE_HEAD` still prints ` --abort-merge` in the copy-paste line |
| A12 `aitask_lock.sh:195` | `ls-tree` | acquisition **refused**; the other session's lock file **unchanged** on the locks branch | an absent lock still acquires; an existing live lock still emits `LOCK_LIVE_HOLDER` |

Suites: the first five rows run in `tests/test_merge_lock_broker.sh` /
`tests/test_merge_broker_rendered_verdicts.sh`; A12 in `tests/test_task_lock.sh`.
Each row additionally gets the probe-only **mutant control** required of every
child (see the shared contract above), so a passing fail-closed assertion is
proved to be observing the fix rather than an unrelated refusal.

The A12 permit row is load-bearing: `test_task_lock.sh` and
`tests/test_lock_live_holder_gate.sh` must stay green, or the fix has traded a
fail-open mutex for one that refuses legitimate claims.

---

## Verification

### Parent (this task)

The parent implements no code. Its acceptance is the decomposition itself:

- Six child task files exist with plans under `aiplans/p1747/`, each
  self-contained enough to execute in a fresh context.
- `aidocs/framework/failopen_git_probes.md` is specified by t1747_1 with the
  Group A table, the negative-space table, and Group C.
- The parent reverts to `Ready` with `children_to_implement` populated, and its
  lock is released.

### Each code child (2-6) — the shared contract

Inherited from t1733's reference implementation, and each child's plan restates
it against its own sites:

- A **negative control** observing the fail-open behavior against a mutant that
  regresses **only the probe**, following `tests/test_fold_mark.sh`'s
  `install_prefix_amend_probe`: it fails loudly if its anchor is stale, verifies
  its own substitution landed, and asserts the rest of the guard survived — so a
  control can never pass vacuously, nor observe "no guard" instead of "fail-open
  guard".
- **Fixture preconditions asserted, not assumed**, in the test *and* its
  control. "The probe returned empty" is a symptom several unrelated fixture
  accidents produce, so each fixture pins both its identity and its symptom.
- A **discriminating case that is production-reachable**: the fixture must be
  one where the destructive action **would otherwise have succeeded**, so the
  test proves a failed probe does not authorise it — not merely that something
  failed. For A1 that is a rebase state where `rebase --skip` legitimately
  applies (the empty-patch case the fallback exists for); for A9, a tree where
  the baseline would otherwise have protected named foreign files.
- **Every consumer is enumerated, not just the one the audit named.** These
  probes are shared helpers, and hardening a helper while some caller still
  reads it bare leaves the site looking fixed and behaving unchanged. Each
  child's plan carries a **call-site table** for every helper it touches, states
  each consumer's disposition on "unverified", and ships a test asserting the
  file's actual call sites equal that table — so a new consumer cannot be added
  unguarded. This bites beyond child 6: `aitask_sync.sh`'s `_sync_gitdir` (A10)
  reaches four more sites through `_quarantine_path`, and
  `aitask_setup.sh`'s `_ait_list_framework_changes` (A9) has four callers in two
  opposite polarities.
- **The unverified state travels on the exit status, never on stdout** wherever
  the value is consumed arithmetically or as a path. Child 6 documents why a
  magic stdout value is unsafe in both spellings; the same rule binds every
  child.
- The **permit direction stays green** — a tightened probe must not start
  refusing legitimate operations.
- Fault injection goes through the **documented seams** already in the tree: the
  argv-keyed `PATH` `git` shim (`tests/test_sync_branch_mode_automerge.sh`
  `install_failing_advance_shim`, `tests/test_fold_mark.sh`
  `install_failing_show_shim`) and `aitask_setup.sh --source-only`.

### Suites each child must run

```bash
bash tests/test_sync_branch_mode_automerge.sh   # t1747_2, t1747_3
bash tests/test_sync.sh                         # t1747_3
bash tests/test_setup_git.sh                    # t1747_4
bash tests/test_fold_mark.sh                    # t1747_5
bash tests/test_issue_import_amend_guard.sh     # t1747_5
bash tests/test_merge_lock_broker.sh            # t1747_6 (A8, A8b)
bash tests/test_merge_broker_rendered_verdicts.sh   # t1747_6 (A8, A8b)
bash tests/test_merge_lock_concurrency.sh       # t1747_6 (A8, A8b)
bash tests/test_task_lock.sh                    # t1747_6 (A12)
bash tests/test_lock_live_holder_gate.sh        # t1747_6 (A12 permit direction)
bash tests/test_lock_reclaim.sh                 # t1747_6 (A12 permit direction)
bash tests/test_stale_lock.sh                   # t1747_6 (A12 permit direction)
bash tests/test_no_unscoped_task_commit.sh      # t1747_3, t1747_4
shellcheck .aitask-scripts/<the file it touched>
```

Shellcheck baseline measured now, so a child can tell its own findings from
pre-existing ones: `aitask_sync.sh`, `lib/task_automerge.sh` and
`aitask_merge_task.sh` are clean apart from SC1091; `aitask_lock.sh` has one
pre-existing SC2086 at `:701`; `aitask_setup.sh` carries pre-existing SC2015 /
SC2034 / SC2129 / SC2295 notes. New code must add none.

Step 9 (Post-Implementation) handles cleanup, archival and merge.

## Risk

### Code-health risk: low

- The parent writes no code; its blast radius is task/plan files plus one new
  aidocs page. · severity: low · → mitigation: none needed.
- The decomposition could under-cover the class if a child is later dropped —
  the audit table is the record that makes that visible. · severity: low · →
  mitigation: none needed; t1747_1 lands the table first, before any code child.

### Goal-achievement risk: medium

- The sweep is a grep-and-read over `.aitask-scripts/**/*.sh`. It catches the
  common single-command shape; a probe assembled through a variable or across
  statements would not be seen, so "every site" is a claim about what this
  method reaches, not a proof of absence. · severity: medium · → mitigation:
  covered by t1747_1 — the doc states its detection boundary explicitly instead
  of claiming exhaustiveness.
- Group C (swallowed *mutation* failures) is real, adjacent, and deliberately
  out of scope; leaving it unnamed would let a reader believe the class is
  closed. · severity: medium · → mitigation: covered by t1747_1 — recorded in
  the doc as named future work.
- The decomposition can silently under-cover the audit: a Group A row assigned
  to no child would let the parent complete with its "every authorizing probe"
  goal false. This was a real defect in the first draft of this plan — A12 was
  audited and then left unassigned. · severity: medium · → mitigation: covered
  by t1747_1 — the Coverage map above partitions every row to a child, and
  t1747_1's doc carries the same map so the check outlives this plan.
- A *within-site* version of the same gap: a helper can be hardened while some
  of its consumers keep reading it bare, so the site looks fixed and is not.
  This too was a real defect in an earlier draft — child 6 specified 3 of the
  ~20 consumers of `aitask_merge_task.sh`'s probe helpers. · severity: medium ·
  → mitigation: none needed as a separate task — every child's plan must carry a
  **call-site table** for each helper it changes plus a test asserting the file's
  actual call sites equal that table, which is what makes "all consumers" a
  checkable claim rather than a promise.
- Five code children means five separate red windows in a shared repo where
  other sessions are editing `lib/task_utils.sh` right now. · severity: low ·
  → mitigation: none needed — children are file-disjoint and sibling-ordered.

**No `### Planned mitigations` block:** both goal-achievement mitigations are
already scoped work inside child t1747_1, not additional tasks, so spawning a
separate mitigation task would duplicate them. The remaining risks are `low` and
self-contained.
