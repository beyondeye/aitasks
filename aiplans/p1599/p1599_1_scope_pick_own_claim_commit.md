---
Task: t1599_1_scope_pick_own_claim_commit.md
Parent Task: aitasks/t1599_scope_task_data_commits_to_their_own_paths.md
Sibling Tasks: aitasks/t1599/t1599_2_scope_fold_mark_commit_and_guard_amend.md, aitasks/t1599/t1599_3_sync_per_task_commits_and_live_lock_skip.md, aitasks/t1599/t1599_4_sweep_latent_unscoped_commits_and_tripwire.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-25 16:56
---

# p1599_1 — Scope the claim commit in `aitask_pick_own.sh`

## Context

`aitask_pick_own.sh` runs on **every task claim**. Its `commit_and_push()` stages
the whole `aitasks/` tree and commits the **entire git index**, so any file a
concurrent session is mid-edit on is swept into a commit whose message names a
different task. Measured on the live `aitask-data` branch: **83 of the last 300**
`ait: Start work on t…` commits (28%) carry a foreign task file; worst case
`c1427200b` (claiming t1405) swallowed **178** — an `ait board` boardidx reshuffle
landing under an unrelated claim.

This is the highest-frequency of the three sites t1599 covers. This child owns
`.aitask-scripts/aitask_pick_own.sh` **and nothing else** — `aitask_sync.sh`
(t1599_3), `aitask_fold_mark.sh` (t1599_2) and the t1599_4 sweep targets are off
limits.

*(Live confirmation during this pick: the data branch was dirty with t1603's
`boardcol`/`boardidx` reshuffle. It was committed separately, under its own
message, so this claim would not swallow it.)*

## Verification of the existing plan (verify pass)

Every line reference in the task and plan re-checked against HEAD — all still
accurate:

| claim | status |
|---|---|
| `commit_and_push()` at `:360-374`, call site `:475` | ✅ |
| `task_file` local + `resolve_task_file` at `:395-396` (`\|\| true`) | ✅ |
| `EMAILS_FILE` at `:68`, `store_email()` at `:232-237` | ✅ |
| `aitask_attach.sh:196-205`, `aitask_gate_record.sh:81-82`, `aitask_gate.sh:1025-1032` | ✅ |
| `task_git` at `lib/task_utils.sh:181-189` — transparent pass-through | ✅ |
| `tests/test_lock_force.sh:37-91` `setup_paired_repos`; `test_gate_record.sh:83-96`/`:100-107`; `test_archive_no_overbroad_add.sh:154-167` | ✅ |
| `grep -rn 'Start work on t' tests/` → zero hits; `tests/test_pick_own_scoped_commit.sh` absent | ✅ |
| "only two data-branch paths are written by a claim" | ✅ — `sync_remote` (`:180`) calls the lib `task_sync`, which only pulls/rebases; it is **not** `aitask_sync.sh`. `commit_and_push` is the script's only commit. But *written by a claim* ≠ *written by **this** claim* — see delta 0. |

Five **deltas** the verify pass adds (each backed by a site already in the repo):

0. **`emails.txt` must be committed only when *this* claim wrote it** — the
   plan's `[[ -f "$EMAILS_FILE" ]]` reproduces the very defect in miniature.
   Confirmed against the code: `store_email` runs at `:421`, **before**
   `acquire_lock` at `:427`, and the lock-refusal branches `exit 1` at
   `:448`/`:454` (and `die` at `:450`). So a blocked or failed concurrent claim
   leaves a **new address appended and uncommitted**. Because `-f` is true
   forever after, the *next* successful claim — including one passing **no
   email at all** — commits that foreign line under its own
   `ait: Start work on t<other>` message. See Step 0 below.
0a. **`emails.txt` cannot be in the claim commit at all.** Authorship of an
   *append* is not ownership of the file's *snapshot*. Two claims for
   **different** task IDs hold **different** task locks, so nothing serializes
   them: both can append (`:421`) before either commits (`:475`), and whichever
   commits first carries **both** addresses under its own
   `ait: Start work on t<N>` message. `EMAIL_STORED` does not close this — the
   flag is true for both sessions. Path-scoping a **shared global file** cannot
   produce per-claim provenance at all. See Step 2a.
0c. **`store_email`'s read-modify-write loses updates.** `echo >>` is an atomic
   append, but `sort -u "$f" -o "$f"` **snapshots** the file and renames its
   output over the target — so with A and B appending concurrently, A's sort can
   read `[seed, alice]`, B appends `bob`, and A's rename **erases bob**. B then
   commits an `emails.txt` that does not contain B's own address. The repo states
   this rule itself: `lib/atomic_write.sh:6-12` — *"a caller that
   read-modify-writes a shared file must hold its own mutex"*. Pre-existing, but
   Step 0 touches this exact function and Step 2a persists its output, so it is
   fixed here rather than scoped out. See Step 0.
0b. **The negative control needs a mechanism, not an instruction.** "Run it
   against the pre-fix code" is unrepeatable once the fix lands, and a
   regression test nobody can falsify proves nothing. See "Negative control" in
   Verification — the fixture builds the pre-fix binary itself.

1. **`-o` on the commit.** The parent task's own suggested fix says
   `task_git commit -o -- <paths>`. `-o`/`--only` is implied by a pathspec, but
   `git commit -o` with *no* pathspec is a hard error — so it converts the
   empty-array catastrophe (a silent whole-index commit, re-creating the exact
   bug) from silent to loud, behind the explicit guard.
2. **Do not fail open on an unverifiable `git status`.** The plan's snippet is
   `[[ -z "$(task_git status --porcelain -- … 2>/dev/null)" ]]`, which reads a
   *failing* status as "nothing to commit" and silently skips the claim commit.
   `aitask_gate.sh:1024-1027` — the site the plan cites as "the cleanest scoped
   no-op guard" — captures the status exit separately for exactly this reason
   ("a failing status with empty stdout must read as unverified, never as
   clean"). Copy that, not just its pathspec.
3. **`[[ -f "$task_file" ]]`, not `[[ -n … ]]`.** `resolve_task_file` also
   searches archived dirs and `old.tar.zst` bundles, so it can return a
   non-existent on-disk path. `main()` itself already guards with
   `[[ -n "$task_file" && -f "$task_file" ]]` at `:398` and `:412`; the array
   build should match.

## Step 0 — Make `store_email()` report whether it wrote (`:227-238`)

Two independent problems in one function: it cannot say **whether it wrote** —
and membership is the real predicate, since re-adding a known address changes no
content — and its `echo >> ; sort -u -o` is an unserialized read-modify-write
that silently drops a concurrent session's address. The "did I write" answer goes
in a global, not a return code: a `return 1` would trip `set -euo pipefail` at
the `:421` call site.

Reuse the canonical mutex rather than inventing one — `lib/registry_lock.sh`
already guards exactly this shape (project registry, agent marks, attachment
manifests), and `ait_lock_dir` (`lib/stale_lock.sh:101`) gives a per-user,
per-repo path under `$TMPDIR` with `AITASKS_LOCK_DIR` as its documented test
seam. Keeping the lock **outside** the tracked tree matters: a `.lockd` beside
`emails.txt` would sit in `aitasks/metadata/` where `aitask_sync.sh`'s
`add aitasks/` sweep (t1599_3's target) would commit it.

```bash
# shellcheck source=lib/registry_lock.sh
source "$SCRIPT_DIR/lib/registry_lock.sh"

# Set by store_email() when THIS invocation added a new address — the only
# condition under which the contributor list is this claim's to persist. A claim
# refused at the task lock (:448/:454) still leaves its append on disk, and a
# later claim must not commit that foreign line under its own task message.
EMAIL_STORED=false

store_email() {
    local email="$1"
    [[ -z "$email" ]] && return 0
    local dir
    dir=$(dirname "$EMAILS_FILE")
    mkdir -p "$dir"
    touch "$EMAILS_FILE"
    grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null && return 0   # fast path

    # `echo >> ; sort -u -o` is a read-modify-write: sort SNAPSHOTS the file and
    # renames its output over the target, so a concurrent session's append made
    # after that snapshot is erased. Atomicity is not serialization
    # (lib/atomic_write.sh:6-12) — hold the mutex, or do not write at all.
    local lockdir
    lockdir="$(ait_lock_dir emails)" || return 0
    if ! registry_lock_acquire "$lockdir" 10 store_email; then
        warn "contributor list busy — email not recorded: $(registry_lock_describe "$lockdir")"
        return 0        # best-effort: never fail a claim over the email list
    fi
    local rc=0
    {
        # Re-check under the lock: a holder we waited on may have added it.
        if ! grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null; then
            printf '%s\n' "$email" >> "$EMAILS_FILE"
            sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
            EMAIL_STORED=true
        fi
    } || rc=$?
    registry_lock_release "$lockdir"
    return 0
}
```

On busy it **skips the write** rather than proceeding unlocked — the stance
`aitask_agent_marks.sh:71-73` states ("a write without the lock is exactly the
lost-update this mutex exists to stop"), adapted to a best-effort caller: the
claim must still succeed. The `{ … } || rc=$?` wrapper guarantees the release
runs under `set -euo pipefail`. Confirm at implementation that sourcing
`registry_lock.sh` also exposes `ait_lock_dir`, and never call
`registry_lock_acquire` inside a command substitution (`stale_lock.sh:43-47`).

Sortedness is preserved deliberately: the `default_email: first` profile option
resolves to the *first line* of `emails.txt` (`aitask_lock.sh:625`,
`board/aitask_board.py:197`), so an append-only file would silently change which
address that picks — and those readers belong to other files this child does not
own.

`EMAIL_STORED` is necessary but **not sufficient** — it decides *whether* to
persist the list at all, not *which commit* it may ride in. That is Step 2a.

## Step 1 — Pre-phase (risk mitigation): `partial_commit_worktree_semantics`

**Do this first, before any scoping edit.**

`git commit -m <msg> -- <paths>` is a **partial** commit: it takes those paths'
**worktree** content and ignores their index entry. The other three children
inherit this pattern, so pin the semantic before propagating it.

Add to `tests/test_pick_own_scoped_commit.sh`: stage the task file, modify it
again on disk, claim, and assert **which** version landed in the commit. State
the determined answer explicitly in the test's header comment.

## Step 2 — Extract one scoped-commit helper

Both commits below need the same three things (stage-so-the-pathspec-can-match,
a scoped no-op guard, a partial commit), so factor them once — mirroring
`_attach_commit` (`aitask_attach.sh:196-205`):

```bash
# _commit_scoped <msg> <path>... — stage and commit ONLY these paths (partial
# commit). Returns 0 = committed, 2 = verified nothing to commit, 1 = failed.
_commit_scoped() {
    local msg="$1"; shift
    # Load-bearing: `git commit --` with no pathspec commits the WHOLE index,
    # silently re-creating the cross-session swallow this fix exists to stop.
    (( $# )) || return 2

    # `add` is needed ONLY so an untracked path can be named by the pathspec;
    # a pathspec cannot match a file git does not know about.
    task_git add -- "$@" >/dev/null 2>&1 || true

    # Capture the status exit separately: a failing status with empty stdout
    # must read as "unverified", never as "clean" (aitask_gate.sh:1024-1027).
    local st st_rc=0
    st="$(task_git status --porcelain -- "$@" 2>/dev/null)" || st_rc=$?
    if [[ $st_rc -eq 0 && -z "$st" ]]; then
        return 2
    fi
    [[ $st_rc -ne 0 ]] && warn "git status failed for $* — committing anyway"

    task_git commit -o -m "$msg" --quiet -- "$@" || return 1
}
```

`-m` must come **before** the `--` pathspec or git reads the message as a path.
The unverifiable branch neither fails open (it commits) nor fails hard (the
caller warns rather than letting `set -euo pipefail` at `:54` abort after the
lock and status write already landed).

Confirm empirically that `git commit -o -m msg --` with an empty pathspec errors
rather than committing the index; if it does not, drop `-o` and rely on the
explicit guard alone.

## Step 2a — Give `emails.txt` its own commit, never the claim's

`aitasks/metadata/emails.txt` is a **shared global** append-only list. Nothing
serializes two claims of different tasks — they hold different task locks — so
both can append before either commits, and any claim-scoped commit that includes
the file carries the other session's address under this task's message. Scoping
by path cannot fix a file that is not task-owned; only a commit message that is
**true regardless of who appended** can.

```bash
commit_and_push() {
    local task_id="$1"; shift
    local paths=( "$@" )
    local rc

    # The contributor list rides in its OWN commit. Concurrency means it may
    # carry another session's address too — which is why the message names no
    # task. Doing this inside the claim commit is what misattributes it.
    if [[ "$EMAIL_STORED" == true ]]; then
        rc=0; _commit_scoped "ait: Record contributor email" "$EMAILS_FILE" || rc=$?
        [[ $rc -eq 1 ]] && warn "could not commit ${EMAILS_FILE}"
    fi

    # The claim commit — task file only. Committed LAST so HEAD is the claim.
    rc=0
    _commit_scoped "ait: Start work on t${task_id}: set status to Implementing" \
        ${paths[@]+"${paths[@]}"} || rc=$?
    case $rc in
        2) info "No changes to commit (task may already be in Implementing status)" ;;
        1) warn "could not commit the t${task_id} claim" ;;
    esac

    # Push is best-effort — network failure should not block the workflow
    task_push
}
```

Order matters only for the `git log -1` contract: the claim commit goes last so
HEAD remains the claim, which the workflow and the tests below read.

**The mutex covers the write, not the commit — deliberately.** Step 0 serializes
the *read-modify-write* because an unserialized one loses data. Extending it to
span the **commit** as well is rejected: it would hold a cross-process lock
across git operations on every claim, and it buys nothing, because the
task-agnostic message is already true when a commit carries two sessions'
addresses. `emails.txt` is an idempotent, order-independent, deduplicated set —
a commit carrying two appends is **accurate**, not a lost update. What *would*
be a lost update is the unlocked `sort -o` rewrite, and that is closed in Step 0.

## Step 3 — Thread the paths from the call site (`:475`)

Exactly two data-branch paths are *written* by a claim: the task file
(`resolve_task_file`, `:396`) and `aitasks/metadata/emails.txt` (`EMAILS_FILE`
`:68`, written by `store_email()` `:232-237`) — but only the first is
**task-owned**, so only it belongs in the claim commit. Lock artifacts are blobs on the
orphan `aitask-locks` branch (plumbing only, never in the data index),
`.aitask-gates/<id>/change_baseline` is gitignored and written *after* the
commit, and `active_gates` is committed separately by the already-scoped
`aitask_gate.sh materialize-active`.

`task_file` is a `local` in `main()`, so thread it in:

```bash
    local commit_paths=( )
    [[ -f "$task_file" ]] && commit_paths+=( "$task_file" )
    commit_and_push "$TASK_ID" ${commit_paths[@]+"${commit_paths[@]}"}
```

`emails.txt` is **not** threaded here — it is not the claim's to commit (Step
2a), and `commit_and_push` handles it separately off `EMAIL_STORED`.

The `${arr[@]+"${arr[@]}"}` form is required — a bare `"${arr[@]}"` on an empty
array trips `set -u` on older bash.

## Verification

New `tests/test_pick_own_scoped_commit.sh` — **nothing asserts this commit
today**. Conventions: header/footer per `tests/test_lock_force.sh`; source
`tests/lib/test_scaffold.sh` then `tests/lib/asserts.sh`; assertion argument
order `assert_contains <desc> <needle> <haystack>`. The
`(cd "$TMPDIR/local" && …)` command-substitution form keeps asserts at top
level, so the `assert_counters_init` subshell opt-in is **not** needed.

- Fixture: copy `setup_paired_repos` from `tests/test_lock_force.sh:37-91`, then
  `aitask_lock.sh --init` as its tests do.
- Seed and commit a bystander `aitasks/t2_bystander.md`, then leave an
  uncommitted edit on it.
- Claim t1: `./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com"`.
- Assert:
  - `git log -1 --pretty=%s` == `ait: Start work on t1: set status to Implementing`
  - `git show --name-status --pretty=format: -M0 HEAD` contains **only** t1's
    paths and **not** `t2_bystander`
  - the bystander is still ` M` unstaged (`test_archive_no_overbroad_add.sh:154-167` shape)
- Idempotent re-claim → no new commit (`rev-list --count`,
  `test_gate_record.sh:100-107`).
- Step 1's characterization assertions.

### `emails.txt` — never in a claim commit

**The invariant, asserted directly:** no commit whose subject matches
`^ait: Start work on t` touches `aitasks/metadata/emails.txt`. It holds under
every interleaving, which is what makes it testable without controlling the race.

1. **Refused-claim residue (production-reachable).** Seed `emails.txt` committed
   with `alice@test.com`; lock t1 as `bob@test.com`; run
   `aitask_pick_own.sh 1 --email "mallory@test.com"` → `LOCK_FAILED`, exit 1.
   Assert the precondition (` M aitasks/metadata/emails.txt`) before continuing —
   a cleanup assertion over unseeded state is vacuous. Unlock, claim t1 as
   `alice@test.com` (already known → `EMAIL_STORED` false). Assert `emails.txt`
   is in **no** commit and is still ` M` unstaged with mallory's line on disk.
2. Same with **no** `--email` at all → unchanged.
3. **Positive direction.** From a clean tree, claim t1 as a **new** address.
   Assert: `git log -1 --pretty=%s` is the **claim** subject; the claim commit
   touches **only** t1's task file; and a **separate** commit
   `ait: Record contributor email` touches **only** `emails.txt`. Without this,
   cases 1–2 pass vacuously (a fix that never commits the list at all).
4. **Interleaved two-task claim.** Append `bob@test.com` to `emails.txt` exactly
   as a concurrent `store_email` would (`echo >>` then `sort -u -o`, uncommitted),
   then claim **t1** with a different new address `alice@test.com`. Assert the t1
   claim commit contains only t1's task file, and that the
   `ait: Record contributor email` commit carries **both** addresses — accurate,
   because its message names no task.
5. **Mutex boundary (deterministic — replaces a background race).** Point
   `AITASKS_LOCK_DIR` at the fixture, pre-create the `emails` lock dir with a
   **live** holder pid so `registry_lock_acquire` reports busy, then claim t1
   with a **new** address and a short timeout. Assert: the run still prints
   `OWNED:1` (the claim is never failed by a busy email list), `emails.txt` is
   **unchanged** (no unlocked write), no `ait: Record contributor email` commit
   exists, and the warning is emitted. Release the lock, re-claim, and assert the
   address now lands — pinning both sides of the boundary rather than leaving
   the assertion shape open.

**No background/`wait` concurrency test.** Two real claims contend on the same
`.git/index.lock`, so one can legitimately fail its commit; a case that requires
both to print `OWNED:` is flaky, not scheduling-independent. Case 4 reproduces
the interleaved *state* deterministically and case 5 exercises the mutex
directly. The lost-update window itself is not deterministically reproducible
from the outside — it is closed by construction (no write without the lock) and
that construction is what case 5 pins.

### Negative control (required — and executable)

The fixture builds the **pre-fix binary itself**, so the control re-runs on every
suite run instead of being a one-off instruction that expires when the fix lands.
The fixture already *copies* `aitask_pick_own.sh` into a throwaway repo, and the
script's last line is the single `main "$@"` at `:535` — so appending a legacy
`commit_and_push` definition ahead of that line makes bash use it, with no edit
to the real function:

```bash
# Rebuild the fixture's COPY with the pre-fix (index-wide) commit_and_push.
install_prefix_commit_and_push() {
    local script="$1/local/.aitask-scripts/aitask_pick_own.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"       # portable; no sed -i
    cat >> "$tmp" <<'LEGACY'
commit_and_push() {
    local task_id="$1"
    task_git add aitasks/
    if task_git diff --cached --quiet; then
        info "No changes to commit"
    else
        task_git commit -m "ait: Start work on t${task_id}: set status to Implementing" --quiet
    fi
    task_push
}
LEGACY
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}
```

Then run the identical bystander scenario against it and assert the defect is
**positively present** — `assert_contains "… bystander IS swept (pre-fix)"
"t2_bystander" "$commit_files"` — rather than merely asserting the fixed
assertion fails. A positive pin fails loudly if the injection silently did not
take effect, which is the way negative controls usually rot. Also assert the run
still printed `OWNED:1`, so a control that aborted early cannot masquerade as
proof.

Run the same control for the `emails.txt` cases: pre-fix, the foreign address
**is** in the claim commit, and no `ait: Record contributor email` commit exists.

`shellcheck .aitask-scripts/aitask_pick_own.sh`.

## Risk

### Code-health risk: medium
- An empty `paths` array turns `commit --` back into a whole-index commit, silently re-creating the exact bug being fixed. · severity: high · → mitigation: explicit empty-array guard + `-o` (which errors on an empty pathspec) + a regression test that a no-path invocation commits nothing
- `commit -- <pathspec>` is a **partial** commit that takes worktree content and ignores the index entry for those paths — a real behaviour change from today's index-wide commit, inherited by the other three children. · severity: medium · → mitigation: inline pre-phase partial_commit_worktree_semantics
- A scoped no-op guard written as `[[ -z "$(status … 2>/dev/null)" ]]` fails **open**: an erroring `git status` reads as "clean" and the claim commit is silently skipped, leaving the status write uncommitted. · severity: medium · → mitigation: capture the status exit separately (`aitask_gate.sh:1024-1027` shape) and treat unverifiable as "attempt the commit", tolerating its failure with a warning
- Scoping the commit by **file existence** rather than **authorship** re-creates the defect on `aitasks/metadata/emails.txt`: `store_email` writes at `:421` before the lock is acquired at `:427`, so a refused claim (`exit 1` at `:448`/`:454`) leaves a foreign address uncommitted for the next claim — even a claim with no email — to sweep under its own task message. · severity: high · → mitigation: `EMAIL_STORED` authorship flag (Step 0) + the refused-claim regression case, driven through the real `LOCK_FAILED` path
- Deeper: `emails.txt` is a **shared global** file with no task owner, and two claims of *different* tasks pass *different* task locks — so both can append before either commits and path-scoping still misattributes. Authorship of an append is not ownership of the snapshot; `EMAIL_STORED` alone does not close this. · severity: high · → mitigation: Step 2a gives the list its own task-agnostic commit, so no `Start work on t<N>` commit can ever contain it; pinned by the interleaved and mutex-boundary cases
- `store_email`'s `echo >> ; sort -u -o` is an unserialized read-modify-write: sort snapshots the file and its `-o` rename erases a concurrent session's newer append, so an address can be **silently lost** — and the losing session still sets `EMAIL_STORED` and commits a list without its own address. Pre-existing, but Step 0 rewrites this function and Step 2a persists its output. · severity: high · → mitigation: serialize on the canonical `lib/registry_lock.sh` mutex at a per-repo `ait_lock_dir emails` path, re-check membership under the lock, and skip the write entirely (never write unlocked) when the mutex is busy; pinned by the mutex-boundary case
- Adding a mutex to the claim path introduces busy / stale / unavailable states on a hot path. · severity: medium · → mitigation: the lock guards only the email-list write, never the task lock, the status write or the commits; a busy mutex degrades to "email not recorded" with a warning and the claim still returns `OWNED:` — asserted directly in the boundary case
- Splitting into two commits changes the claim's commit shape (a new-contributor claim now produces two commits) and adds a `_commit_scoped` helper. · severity: low · → mitigation: HEAD remains the claim commit (ordering is explicit), the extra commit only fires when a genuinely new address is added, and the `git log -1` contract is asserted in the positive-direction case
- Blast radius is now three functions and one call site in one script; no shared helper changes. `store_email`'s early-return-on-known-address means it no longer rewrites the file, but the resulting content is identical either way. · severity: low · → mitigation: covered by the positive-direction emails.txt case

**Accepted residual — what this does not buy (2).** `git log -- emails.txt`
still cannot attribute an individual address to a session, because a single
commit may carry two concurrent appends. That is inherent to a shared,
order-independent, deduplicated list and is outside t1599's scope; what the fix
guarantees is that no *task* commit ever claims it.

**Accepted residual — what this does not buy.** git refuses a partial commit
during an in-progress merge ("cannot do a partial commit during a merge"), where
today's index-wide commit would succeed. In branch mode this is unreachable:
`assert_data_worktree_clean` (`lib/task_utils.sh:108-136`) `die`s on `MERGE_HEAD`
before `task_git` ever runs git. In legacy mode that guard no-ops
(`_ait_data_gitdir` returns empty), so a claim inside a mid-merge repo now fails
where it previously committed. Accepted: a data repo wedged mid-merge is already
broken, and failing loudly there is better than committing a merge's whole index
under a claim message.

### Goal-achievement risk: medium
- `resolve_task_file` also searches archived dirs and `old.tar.zst` bundles, so it can return a path that does not exist on disk; a `-n`-only guard would then name a bogus pathspec and silently commit nothing. · severity: medium · → mitigation: guard with `[[ -f "$task_file" ]]`, matching `main()`'s own `:398`/`:412` checks
- A bystander can still be swept by the other two unscoped sites (`aitask_sync.sh`, `aitask_fold_mark.sh`), so the production foreign-file rate does not reach 0% from this child alone. · severity: low · → mitigation: out of scope by design — owned by t1599_2/t1599_3, with t1599_4 as the sweep + tripwire
- A negative control expressed as an instruction ("run it against the pre-fix code") is unrepeatable once the fix lands, leaving a regression test that passes forever without ever having been shown able to fail. · severity: medium · → mitigation: the fixture builds the pre-fix binary itself (`install_prefix_commit_and_push`) and pins the defect **positively**, so the control runs on every suite run
- The 0%-foreign-rate verification is a lagging indicator, meaningful only after enough new claims accumulate. · severity: low · → mitigation: t1604 (`verify_zero_foreign_rate_after_soak`), already spawned by the parent

### Planned mitigations
- timing: pre-phase | name: partial_commit_worktree_semantics | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: partial commit takes worktree content, not the index entry | desc: Characterization test pinning which version of a staged-then-modified path a path-scoped commit captures. | disposition: inline (Step 1 of this plan)
