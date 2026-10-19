---
Task: t1739_gateway_pull_policy_and_git_argv_parser.md
Base branch: main
Output branch: main
---

# t1739 — `./ait git pull` cleanup + git argv parser

## Context

t1725_1 made the workflow pull (`_task_pull_rebase`) abort a conflicted rebase
it can prove it started. The supported gateway `./ait git pull` still runs a raw
`git pull` through `task_git` (`ait:345-358`), so a conflict through it leaves
`rebase-merge` behind, and then every later `./ait git` write is refused.

All three defects come from one cause: routing keys on `$1`, but git accepts
global options before the subcommand:
- `ait` would miss `git -c x pull` even after a `$1 == pull` test was added;
- `_ait_git_subcmd_is_readonly` / `_ait_git_subcmd_is_recovery`
  (`lib/task_utils.sh:308/330`) key on `${1:-}`. So
  **`./ait git -c core.pager=cat rebase --abort` is refused today**, and that
  is exactly the recovery the guard's own die message advertises.

Outcome: a single parser for argv shape. The gateway pull goes through the same
five-signal ownership pipeline as the workflow pull. The guard classifies
option-prefixed calls correctly. Options that redirect git to another repo are
rejected at the gateway.

## Probed facts that shape the design

- git 2.56: `--git-dir X`, `--work-tree X`, `--namespace X`, `--config-env X`,
  `--attr-source X` all accept a **separated** value; `-Cfoo` is rejected
  (`-C` is exact-match only). **Bare `--exec-path` takes no value**: it prints
  the exec path and exits (`git --exec-path status` → `/usr/lib/git-core`,
  rc 0). The task lists `--exec-path` as value-taking, which is wrong for the
  bare form. The parser follows git, so bare `--exec-path` consumes nothing.
  `--exec-path=/x status`→2 still holds.
- `aitask_sync.sh:2049` / `:2068` already call
  `task_git "${AIT_RECONCILE_GIT_OPTS[@]}" merge --ff-only …` / `… pull --rebase …`.
  Today `$1=-c` classifies them as neither recovery nor readonly, so the guard
  applies. After the retrofit they classify as `merge --ff-only` / `pull`, which
  are still neither, so their behaviour is **unchanged**. The pre-phase pins
  this before the change and after it.
- No caller uses `./ait git -C/--git-dir/--work-tree/-c` (grep across
  scripts, skills and docs), so rejecting the redirect options breaks no
  caller.

## Pre-phase (risk mitigations)

1. [characterize_guard_global_opts] In `tests/test_task_git.sh`, add **Test 17**
   (same fixture shape as Test 16: `setup_repo_with_remote` +
   `setup_data_branch` + a `probe_17` subshell). With `rebase-merge` planted,
   assert the classifications the retrofit must keep: `-c a=b -c c=d merge
   --ff-only` → refused, `-c a=b pull --rebase` → refused, `push` → refused,
   `status` → allowed, `rebase --abort` → allowed. Each has a clean-worktree
   negative control. Run it green against the **unmodified** library before
   touching `task_utils.sh`, and record the output in the Final Implementation
   Notes.

## Implementation

### 1. `lib/task_utils.sh` — ONE global-option walker (next to `_ait_git_subcmd_is_readonly`)

A single walker classifies the global-option region. The rest are thin readers
of its results, so the value-skip rule exists in exactly one place.

```bash
# Git global options whose value is the NEXT token. The `--opt=value` spelling
# consumes nothing extra. Probed against git 2.56: `-C`/`-c` are exact-match only
# (`-cfoo=bar` is "unknown option"), and bare `--exec-path` takes no value (it
# prints the path and exits).
_ait_git_global_opt_takes_value() {
    case "${1:-}" in
        -C|-c|--git-dir|--work-tree|--namespace|--config-env|--attr-source) return 0 ;;
    esac
    return 1
}

# _ait_git_scan_globals <argv…> — walk git's global-option region once. Results
# in globals (call it directly, NEVER inside $( ) — the assignments would die
# with the subshell):
#   AIT_GIT_SUBCMD_IDX   1-based index of the first non-option token; 0 = none
#   AIT_GIT_REDIRECT_OPT first of -C/--git-dir/--work-tree/--namespace (either
#                        spelling, the name without `=value`), or ""
#   AIT_GIT_CONFIG_OPTS  the config-bearing options, verbatim and in order:
#                        `-c X`, `--config-env X`, `--config-env=X`
#   AIT_GIT_OTHER_OPTS   every other global option (with its value), in order
_ait_git_scan_globals() { … }

# ait_git_subcmd_index <argv…> — prints AIT_GIT_SUBCMD_IDX (0 = the fail-closed
# answer, which classifies as neither readonly nor recovery). ALWAYS returns 0.
ait_git_subcmd_index() { _ait_git_scan_globals "$@"; printf '%s' "$AIT_GIT_SUBCMD_IDX"; }

# ait_git_redirect_opt <argv…> — prints AIT_GIT_REDIRECT_OPT. ALWAYS returns 0.
ait_git_redirect_opt() { _ait_git_scan_globals "$@"; printf '%s' "$AIT_GIT_REDIRECT_OPT"; }
```

### 2. `assert_data_worktree_clean` — retrofit (signatures of both classifiers unchanged)

```bash
    [[ "${AIT_GIT_SKIP_STATE_CHECK:-}" == "1" ]] && return 0
    local idx
    idx="$(ait_git_subcmd_index "$@")"
    # NOT "${@:idx}" unguarded: ${@:0} would prepend $0.
    if (( idx > 0 )); then set -- "${@:idx}"; else set --; fi
    _ait_git_subcmd_is_recovery "$@" && return 0
    _ait_git_subcmd_is_readonly "$@" && return 0
```
Use `set --` rather than an array, so an empty argv never meets `set -u`
(it is function-local). The rest is unchanged.

### 3. One owned-pull core, two callers

Generalize `_task_pull_rebase` (`:1302`) into `_ait_owned_pull <git argv…>`: the
body stays the same (mutex → `before`/`head_before` → `_ait_data_git "$@"` with
`2>&1` capture forwarded to stderr → `_task_pull_rebase_cleanup` absorbing rc 10
→ release). The only change is that the hard-coded argv becomes `"$@"`. Then:

```bash
_task_pull_rebase() {
    _ait_owned_pull "${AIT_RECONCILE_GIT_OPTS[@]}" pull --rebase --no-autostash --quiet
}
```
Every existing caller and test of `_task_pull_rebase` is untouched. There is one
copy of the ownership pipeline, never a second (the "one implementation, two
consumers" rule `ait_rebase_is_ours` already follows).

**Completion postcondition: inside the core, while the mutex is held.** This is
the one addition to the core body. When the final `rc` is 0 (a clean pull, or
cleanup rc 10), and **before** `ait_pull_mutex_release`:

```bash
    if [[ $rc -eq 0 ]]; then
        local unmerged probe_rc=0
        unmerged="$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null)" || probe_rc=$?
        if [[ $probe_rc -ne 0 ]]; then
            printf "aitask: %s: 'git diff' exited %s while checking for unmerged paths - the pulled commits are in place; check './ait git status'\n" \
                "$AIT_PULL_UNVERIFIED_SENTINEL" "$probe_rc" >&2
            rc=1
        elif [[ -n "$unmerged" ]]; then
            printf "aitask: %s: unmerged paths remain in the data worktree - left untouched; resolve them or run './ait git-health'\n" \
                "$AIT_PULL_UNVERIFIED_SENTINEL" >&2
            rc=1
        fi
    fi
```
with the one spelling, next to `AIT_PULL_AUTOMERGED_SENTINEL` and under the
same "one constant, emitter and matchers all read it" rule:
`AIT_PULL_UNVERIFIED_SENTINEL="pull completed but its result could not be verified"`.

- The probe status is captured separately, never `|| true`. An inspection
  failure is its own outcome (rc 1, its own line), never a verified success.
- Each line **describes the completed pull separately from the failed
  inspection**. It never claims "nothing was changed": the pull may already
  have moved HEAD and files, and the line says the pulled commits are in place.
- **No cleanup in either branch.** Neither state is proven ours, so it is
  reported and left alone. The pull's own exit status is overridden only to
  report failure, never to report success.
- Holding the mutex means **no other managed pull** (workflow or gateway) can
  run between our pull and the inspection. An unmanaged writer (`aitask_sync.sh`,
  raw `git`) still could, which is the residual the mutex comment already
  documents. That is why the check reports and never acts.
- Both callers get it. On the workflow path (`--no-autostash` already) it is
  unreachable in practice, but when it fires the callers must **recognize it
  explicitly** (review finding, verified against the current code):

**Caller recognition (reason vocabulary unchanged; no new code reaches
`FAILED:` / `SYNC_FAILED:`):**
- `_task_push_classify`: a new arm on `rebase_err`, **second** (right after
  `pull_locked`, which means no pull ran at all, so the two are disjoint) and
  ahead of every state and `CONFLICT` arm. It maps the sentinel to `unknown`.
  Why it must come first: after a conflict that was auto-merged, the blob still
  carries git's `CONFLICT (content)` text. Without precedence an inspection
  failure would classify as `rebase_conflict`, whose hint falsely says the
  rebase "was aborted".
- New `_task_pull_unverified_line <blob>`: the first sentinel line without its
  `aitask: ` prefix, or nothing. It uses the same grep as
  `_task_pull_report_automerge`.
- `task_sync` failure path: when that line is non-empty, it is the `detail`
  (instead of git's first line), and it is passed to `_task_sync_warn` as a
  second argument. `_task_sync_warn` checks it **first** and warns
  `task data sync: <line>` **regardless of the pending counts**. Verified: today
  the zero-pending branch warns only for
  `dirty_worktree|rebase_conflict|rebase_in_progress|data_midop|pull_locked`, so
  an `unknown` after a successful pull (0/0) would be silent. An unmerged or
  uninspectable worktree is a local-state blocker exactly like those.
- `task_push`: when **any** retry pull in this cycle emitted the sentinel, warn
  `task data push: <line>` on **both** exits, independent of
  `TASK_PUSH_UNPUSHED`. On the failure exit this replaces the git-first-line
  detail. On the success exit (a later push attempt went through) it is the only
  warning, because the uninspected worktree is still a local concern after the
  push succeeds. Reason: `_task_push_warn` is silent at 0 unpushed today, and a
  successful push prints nothing at all.
- Gateway `task_git_pull`: the blob (sentinel line included) is already printed
  to stderr, and the `reason != unknown` warn stays as it is.

### 4. Gateway entry points

```bash
# task_git_gateway <argv…> — what `./ait git <argv>` runs (everything but `push`).
task_git_gateway() {
    local redirect idx
    redirect="$(ait_git_redirect_opt "$@")"
    [[ -n "$redirect" ]] && die "./ait git: '$redirect' points git away from the task-data worktree, which defeats this gateway (and would read pull-ownership evidence from the wrong git-dir). Use plain 'git $redirect …' instead."
    idx="$(ait_git_subcmd_index "$@")"
    if (( idx > 0 )) && [[ "${!idx}" == "pull" ]]; then
        task_git_pull "$@"; return
    fi
    task_git "$@"
}

# task_git_pull <argv…> — the gateway pull, with the workflow pull's cleanup.
task_git_pull() {
    _ait_detect_data_worktree
    assert_data_worktree_clean "$@"          # a pre-existing wedge still dies here
    _ait_git_scan_globals "$@"
    local idx="$AIT_GIT_SUBCMD_IDX" a
    local -a pull_args=("${@:idx+1}")
    # (a) Autostash is refused, never forwarded (see "Autostash" below).
    for a in "${pull_args[@]}"; do
        [[ "$a" == "--" ]] && break
        [[ "$a" == --au* && "--autostash" == "$a"* ]] && die "./ait git pull: '$a' is not supported …"
    done
    # (b) Config the user supplied must reach the continuation and the abort too,
    # with the framework pins LAST so they win (later -c wins). Function-local and
    # dynamically scoped, so ait_automerge_advance and ait_rebase_abort_if_ours —
    # which read AIT_RECONCILE_GIT_OPTS — see the same set.
    local -a framework_opts=("${AIT_RECONCILE_GIT_OPTS[@]}")
    local -a AIT_RECONCILE_GIT_OPTS=("${AIT_GIT_CONFIG_OPTS[@]}" "${framework_opts[@]}")
    local blob rc=0 reason
    blob="$(_ait_owned_pull "${AIT_RECONCILE_GIT_OPTS[@]}" "${AIT_GIT_OTHER_OPTS[@]}" \
                pull --no-autostash "${pull_args[@]}" 2>&1)" || rc=$?
    [[ -n "$blob" ]] && printf '%s\n' "$blob" >&2
    # The completion postcondition already ran inside _ait_owned_pull, under the
    # mutex (step 3), so a non-zero rc here may come from it.
    if [[ $rc -ne 0 ]]; then
        reason="$(_task_push_classify "" "$blob")"
        [[ "$reason" != "unknown" ]] && \
            warn "./ait git pull did not complete (${reason}) — $(_task_push_reason_hint "$reason" "./ait git pull")"
    fi
    return $rc
}
```
- **Autostash (review finding, verified).** An isolated probe of
  `git pull --rebase --autostash` with a dirty tracked file that overlaps the
  incoming change returned **rc 0** and left `UU f.txt` plus a kept
  `stash@{0}`, with no rebase or merge state. The cleanup runs only on non-zero
  rc, so it would never fire. `task_automerge.sh:26-28` also relies explicitly
  on the pull refusing dirty tracked files. So the managed path forces
  `--no-autostash`, inserted **right after `pull`**: command-line wins over
  `rebase.autoStash` / `merge.autoStash` config, whether inherited or passed
  with `-c`. Because a later user flag would override that insertion, a
  user-supplied `--autostash` is **refused**, including git's accepted
  abbreviations (`--au` was probed and is accepted), up to a `--`. The die
  message points at plain `git -C .aitask-data pull --autostash`. A dirty
  worktree then makes the pull refuse, which classifies as `dirty_worktree`.
  The core's completion postcondition (step 3) is defence in depth for any
  other route to an rc-0 unmerged index.
- **Recovery configuration (review finding, verified).** A probe of a rebase
  started with `-c user.name/-c user.email` in a repo with
  `user.useConfigOnly=true` and no identity reached a conflict. Then
  `rebase --continue` with only the framework pins failed with "no email was
  given". So the user's **config-bearing** globals (`-c`, `--config-env`, both
  spellings) are prepended to `AIT_RECONCILE_GIT_OPTS` for the whole call. That
  covers the pull, `ait_automerge_advance`'s `rebase --continue`/`--skip`, and
  `ait_rebase_abort_if_ours`'s `rebase --abort`. The framework-enforced pins
  (`rerere.enabled=false`, `maintenance.auto=false`) stay **last** so they win.
  This is the explicit distinction: user config applies everywhere except where
  it would contradict a pin. Non-config globals (`--no-pager`,
  `--literal-pathspecs`, …) go to the pull only. The local-array override was
  probed: callees see the augmented array, and the global is unchanged
  afterwards. The `AIT_RECONCILE_GIT_OPTS` comment gets a sentence documenting
  this one sanctioned override.
- Merge-mode, rebase-mode and `--rebase=…` choices are passed through verbatim.
- Exit status is git's own. It is 0 only when the pull succeeded and passed the
  postcondition, or when the auto-merge completed the rebase (cleanup rc 10).
- The gateway pull's git output now goes to **stderr**, as the workflow pull's
  does, because the classifier needs both streams in one blob. This is a minor
  user-visible change, noted in the docs.

`ait` git arm (`:345-358`): the `push` branch stays keyed on `$1` exactly as it
is. The `else` branch calls `task_git_gateway "$@"` instead of `task_git "$@"`.

### 5. Stale comments to update (same edit)

- The pull-mutex SCOPE note (`:1056-1061`) and `_task_pull_rebase`'s RESIDUAL
  paragraph (`:1293-1297`): the `./ait git` gateway pull is now covered.
  `aitask_sync.sh` and raw `git` remain uncovered.
- The `AIT_RECONCILE_GIT_OPTS` comment (`:1227-1229`, "task_git's guard reads $1
  …"): the guard now parses past global options. Rewrite the sentence so it does
  not claim the old restriction.

### 6. Explicit bounds, recorded in a comment on `task_git_pull` and in the docs

- **Merge mode is not cleaned up.** A merge-mode gateway pull that conflicts
  leaves `MERGE_HEAD`. Signal 4 reports it as `mid-MERGE_HEAD` →
  `data_midop`, with no rebase wording and no `rebase --abort`. Closing it would
  need its own `ORIG_HEAD` ownership evidence, which is a separate decision.
- **`push` still keys on `$1`.** `./ait git -c x push` runs a raw `git push`
  through the guard. That cannot wedge the worktree, so it is out of scope.
- A gateway pull that conflicts on content it cannot auto-merge is **aborted**,
  so the user cannot resolve it in place. That is the invariant being enforced.
  The escape hatch is plain `git -C .aitask-data pull …`.

### 7. Docs — `website/content/docs/commands/sync.md`

Add an `### ait git pull` subsection after "Task-data pull before task
selection" (before the push-exit paragraph moves under it, or right after it).
It covers: same auto-merge-then-abort behaviour and the same reasons/hints as
the pick-time pull; non-zero exit with git's status; the merge-mode bound
(`MERGE_HEAD` is left in place and reported as `data_midop`); output on stderr.
It also states that automatic stashing is always off (an explicit
`--autostash` is refused, and a dirty data worktree makes the pull refuse with
`dirty_worktree`), and that `-c` / `--config-env` settings apply to the whole
reconciliation (continue and abort included), except the framework's own rerere
and auto-maintenance pins.
Add one sentence under `## ait git push`'s intro paragraph: `-C`,
`--git-dir`, `--work-tree` and `--namespace` are refused (use plain `git`), and
`-c name=value` is kept. Current-state prose only. Then run
`python3 check_links.py --build` in `website/`.

## Tests

**`tests/test_task_git.sh`** (Test 17 is the pre-phase):
- **Test 18 — parser table** (pure function): `pull`→1; `-c a=b pull`→3;
  `--no-pager pull`→2; `-C dir -c a=b rebase --abort`→5; `--exec-path=/x status`→2;
  `--exec-path status`→2; `--git-dir x status`→3; `-c a=b`→0; empty→0. Redirect
  table: `-C d status`→`-C`; `--git-dir=x pull`→`--git-dir`; `--work-tree x pull`
  →`--work-tree`; `-c -C=x status`→empty (a `-c` value is not an option);
  `-c a=b status`→empty; `status -C x`→empty (only the global region is scanned).
- **Test 19 — the latent recovery bug, paired:** with `rebase-merge` planted,
  `-c core.pager=cat rebase --abort` → **allowed** (this is the red proof: it is
  refused on the unmodified library, so run it before step 2 and record that).
  `-c core.pager=cat commit` → **refused**. Clean-worktree controls for both.
- Test 16 runs **unchanged**.

**New `tests/test_ait_git_gateway_pull.sh`** (self-contained; sources
`asserts.sh`, `scratch_cwd.sh`, `git_config_isolation.sh` with
`sync_isolate_git_config`/`assert_git_config_isolated` after the counter init;
copies `ait` + `.aitask-scripts` and runs `setup_data_branch` the way
`test_task_git.sh` Test 7 does, so the **real dispatcher** runs in branch mode;
conflicts are forced on the `aitask-data` branch from a second clone of the
bare remote, in the `force_remote_conflict` shape, on a non-task file
`conflict.txt` so auto-merge cannot resolve it):
- **A — bare form:** `./ait git pull --rebase` → non-zero exit, no wedge (probe
  re-implemented from `ls`, like `probe_wedge`), no `aitask-pull.lock` under the
  data git-dir, stderr contains `rebase_conflict`, and a following `./ait git
  commit` of a probe file succeeds. A clean-before control too.
- **B — option-prefixed form against A's result:** a fresh fixture running
  `./ait git -c core.pager=cat pull --rebase`. Assert that its (exit≠0, wedge,
  lock, reason, next-commit) tuple **equals the tuple computed in A**, not a
  hand-written expectation.
- **C — merge mode:** `./ait git -c pull.rebase=false pull` under the same
  conflict → non-zero, `MERGE_HEAD` **still present**, stderr names
  `data_midop`, and no `aitask:`-prefixed sentinel line or `Warning:` hint line
  contains `rebase`. (git's own lines are excluded: they are git's wording, not
  ours.)
- **D — pre-existing wedge:** `rebase-merge` planted with a foreign orig-head →
  `./ait git pull --rebase` dies in the guard and the wedge survives.
- **E — redirect refusal:** `./ait git -C /tmp status`, `./ait git
  --git-dir=/x pull` → non-zero, message names the option. `./ait git -c
  core.pager=cat status` → succeeds (a `-c` value is preserved).
- **F — mutex busy:** hold `aitask-pull.lock` through `stale_lock_acquire` from a
  live background sleeper → `./ait git pull --rebase` exits non-zero with
  `pull_locked`, and the remote commit is not pulled.
- **G — autostash, inherited config:** a dirty tracked file overlapping the
  incoming change, with `rebase.autoStash=true` set (i) in the data repo's own
  config and (ii) through `./ait git -c rebase.autoStash=true pull --rebase`.
  Each → non-zero, `dirty_worktree`, no unmerged path (`diff --diff-filter=U`
  empty), no new `stash` entry, and the dirty file's bytes unchanged.
  Control: the same fixture through **raw** `git -C .aitask-data -c
  rebase.autoStash=true pull --rebase` shows rc 0 with an unmerged path. That
  proves the fixture reproduces the hazard the gateway closes.
- **H — explicit autostash refused:** `./ait git pull --rebase --autostash` and
  `./ait git pull --rebase --au` → non-zero, message names the flag, and HEAD
  and the remote-tracking ref are unchanged (nothing was fetched or pulled).
  `./ait git pull --rebase -- --autostash`-style tokens after `--` are not
  scanned (parser-level assertion only).
- **I — user config carried through recovery:** set `user.useConfigOnly=true`
  and remove `user.name`/`user.email` from the data repo (the isolated global
  config supplies none). Force a **frontmatter-only** task-file conflict that
  the auto-merge resolves (the `test_task_push.sh` Test 48 shape). Then
  `./ait git -c user.name=T -c user.email=t@t pull --rebase` → rc 0,
  `auto-merged` sentinel, no wedge, and the replayed commit's committer is
  `t@t`. This is the discriminating red case: without (b), the continuation
  fails on identity, the abort runs, and rc≠0.
- **J — postcondition (in `tests/test_task_push.sh`, next to Test 41's runner
  stub, driving `_task_pull_rebase` on a legacy fixture whose real pull
  succeeds).** The stub passes everything through to real git except
  `diff --name-only --diff-filter=U` **while no `rebase-merge`/`rebase-apply`
  exists under the git-dir**. That predicate isolates the postcondition probe,
  because `task_automerge.sh` runs its own `--diff-filter=U` probes (`:209`,
  `:235`) mid-rebase, and those must reach real git. The stub skips the leading
  `-c` pairs the way Test 41's does, and it logs every call it sees:
  - **J1 unmerged:** the stub prints a path, rc 0 → `_task_pull_rebase` returns
    non-zero, and the output names the unmerged-paths line.
  - **J2 probe failure:** the stub exits 128 with empty stdout → non-zero, the
    "could not verify … (git diff exited 128)" line appears, and it is
    **not** reported as success. Classified as `unknown`, not as any state
    reason.
  - **J1/J2 no cleanup:** the call log shows no `rebase --abort`, `reset`,
    `checkout` or `stash` after the probe.
  - **J3 placement:** when the probe runs, the stub records whether
    `<gitdir>/aitask-pull.lock` exists → it must exist (the check runs under the
    mutex). After return the lock must be gone (it is released afterwards).
  - **J0 control:** the real runner (no stub) on the same fixture → rc 0 and no
    postcondition line, so J1/J2 are discriminating.
  - **J4 zero-pending sync reporting:** the remote is one non-conflicting commit
    ahead and there are no local commits. The stub fails the probe (128) →
    `task_sync` → `TASK_SYNC_STATUS=failed`, `TASK_SYNC_REASON=unknown`,
    `TASK_SYNC_UNPUSHED=0`/`UNPULLED=0`, and stderr **contains the sentinel
    line** (warned despite 0/0). HEAD **did** advance to the remote commit, and
    the line says the pulled commits are in place, never "nothing was changed".
    Control: the same scenario with an `unknown` failure that lacks the sentinel
    stays silent at 0/0, which pins that only the sentinel widened the policy.
  - **J5 inspection failure after a successful auto-merge:** the Test 48
    frontmatter-only conflict auto-merges, then the stub fails the post-rebase
    probe → `task_sync` reason is `unknown`, **not** `rebase_conflict`. No
    warning text contains "was aborted". The sentinel line is the detail.
    Control: the identical fixture with the real runner → `synced` +
    `TASK_SYNC_AUTOMERGED=1`.
  - **J6 push surface:** a local commit plus a non-conflicting remote advance,
    so the first push is rejected and the retry pull rebases. The stub fails
    that pull's probe → the next push succeeds (`TASK_PUSH_STATUS=pushed`) and
    stderr still **contains the sentinel line**. Control: the real runner →
    `pushed` with no sentinel line.
  - **Classifier unit (Test 52 neighbourhood):** `_task_push_classify ""
    "<CONFLICT (content) …>\n<sentinel line>"` → `unknown`.
    `"<CONFLICT …>"` alone → still `rebase_conflict` (control).
- **Parser table additions (Test 18):** for `_ait_git_scan_globals`,
  `-c a=b --no-pager --config-env=x=Y -c c=d pull` → CONFIG_OPTS =
  `-c a=b --config-env=x=Y -c c=d`, OTHER_OPTS = `--no-pager`, IDX = 7 (`-c`¹
  `a=b`² `--no-pager`³ `--config-env=x=Y`⁴ `-c`⁵ `c=d`⁶ `pull`⁷).
  `--config-env x=Y status` → CONFIG_OPTS = `--config-env x=Y`.

Regression runs (unchanged files): `bash tests/test_task_push.sh` (Tests
19, 39-52 drive `_task_pull_rebase` through the new core),
`bash tests/test_task_git.sh`, `bash tests/test_sync_deferral_and_quarantine.sh`
and the other `tests/test_sync*.sh` that source `task_utils.sh`, plus
`shellcheck .aitask-scripts/lib/task_utils.sh ait`.

## Verification

1. Pre-phase Test 17 green before any library edit. Test 19's
   allowed-assertion **red** before step 2 (recorded), green after.
2. All test files above pass. Read each file's own summary line.
3. `shellcheck` clean on touched shell files. `check_links.py --build` clean.

## Risk

### Code-health risk: medium
- The `assert_data_worktree_clean` retrofit changes the classification path of every `task_git` call, including `aitask_sync.sh`'s option-prefixed `merge --ff-only` / `pull`. A parser slip (e.g. an unguarded `${@:0}`) would silently open or close the guard on a load-bearing path · severity: low (residual — addressed by inline pre-phase characterize_guard_global_opts plus the Test 19 pair; the level stays medium for blast radius alone: every `task_git` call and every pick runs through the touched code) · → mitigation: inline pre-phase characterize_guard_global_opts
- Generalizing `_task_pull_rebase` into `_ait_owned_pull` touches the pull that runs at every pick and every push retry. The body is unchanged except for the completion postcondition, which also applies to the workflow path: a failing `git diff` probe now turns a successful workflow pull into a reported failure (best-effort callers, so it never aborts a pick). Tests 19/39-52 drive it unchanged, and Test J pins the new branch · severity: low · → mitigation: none
- The gateway pull's git output moves from stdout to stderr. No in-repo consumer parses it · severity: low · → mitigation: none
- The user-config carry relies on a function-local, dynamically scoped override of the global `AIT_RECONCILE_GIT_OPTS`. That is implicit coupling with `task_automerge.sh` and `ait_rebase_abort_if_ours`, and a future callee that copies the array at source time would silently drop user config. It is documented on the constant and pinned end to end by Test I · severity: low · → mitigation: none
- Forcing `--no-autostash` and refusing `--autostash` changes what the gateway accepts. No in-repo caller passes it (grep) · severity: low · → mitigation: none

### Goal-achievement risk: low
- Merge-mode conflicts and option-prefixed `push` are left as explicit bounds, not closed. The task allows a bound, but the "any framework-driven pull" wording is still only met for rebase mode · severity: low · → mitigation: gateway_push_global_opts, gateway_merge_pull_cleanup
- Bare `--exec-path` is treated as no-value, which follows git (probed) rather than the task text. The verification table is unaffected · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_guard_global_opts | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: guard retrofit reclassifies option-prefixed task_git calls | desc: Test 17 pins the guard's classification of aitask_sync.sh's option-prefixed merge/pull plus push/status/rebase --abort, green before and after the retrofit
- timing: after | name: gateway_push_global_opts | type: bug | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: option-prefixed push left as a bound | desc: Decide and implement what `./ait git <global-opts> push` does — route through task_push (best-effort contract) or refuse — instead of a raw git push
- timing: after | name: gateway_merge_pull_cleanup | type: bug | priority: low | effort: medium | inline_risk: high | added_complexity: medium | addresses: merge-mode gateway pull left as a bound | desc: ORIG_HEAD-based ownership evidence so a conflicted merge-mode `./ait git pull` aborts its own merge instead of leaving MERGE_HEAD

## Step 9 (Post-Implementation)

Current-branch mode: commit code (`bug: … (t1739)`) and plan separately via
`./ait git`, then archive per task-workflow Step 9.

## Post-Review Changes

### Change Request 1 (2026-10-18 18:40)
- **Requested by user:** interactive pulls need an explicit support policy. The captured gateway took the terminal from the sequence editor, and an `edit` stop returned 0 with `rebase-merge` left (the postcondition checked only unmerged paths), after which `task_git commit` was refused. Decide and enforce the semantics, including config-selected modes, without blindly aborting an intentional edit stop, and add regression coverage.
- **Changes made:**
  - Chosen policy: **refuse** interactive rebase in the gateway before anything runs. New `_ait_git_pull_cli_rebase_mode` mirrors git 2.56's parsing, probed with a logging sequence editor: the last rebase option wins; bare `--rebase`/`-r` mean `true` and override an interactive config; a short `-r` takes the rest of its cluster (`-qri` is interactive, `-rq` is the value `q`); `-s`/`-X`/`-o` take a required value and `-S`/`-j` an optional attached one; long options abbreviate (`--reb=`); `--` ends options. With no CLI mode, `task_git_pull` reads `branch.<current>.rebase`, then `pull.rebase`, **with the user's `-c`/`--config-env`**. A config read failing other than "not set" refuses (unknown mode). `i`/`interactive` → die naming the source and pointing at plain git.
  - The `_ait_owned_pull` postcondition is widened: after rc 0, any in-progress state (`rebase-merge`, `MERGE_HEAD`, …) is checked **first** and reported via the sentinel ("still mid-<state> - left untouched"), never aborted. This keeps a single mutex exit point.
  - Docs: a "No interactive rebase" bullet in `sync.md`.
- **Tests:** Test 18 gained a 20-row CLI-mode table. Test 64 J7 runs a real interactive `edit` stop through `_ait_owned_pull`: non-zero, sentinel "still mid-rebase-merge", not aborted, mutex released. Gateway Test H covers refusals for `--rebase=interactive`, `-qri`, `-c pull.rebase=interactive`, `--config-env`, `branch.aitask-data.rebase=i`, and branch-over-pull precedence; for each, the editor never ran and nothing was fetched. Its control is `--rebase` over an interactive config, which pulls. Mutants M7 (refusal removed) and M8 (state check removed) are both caught.
- **Files affected:** `.aitask-scripts/lib/task_utils.sh`, `tests/test_task_git.sh`, `tests/test_task_push.sh`, `tests/test_ait_git_gateway_pull.sh`, `website/content/docs/commands/sync.md`

### Change Request 2 (2026-10-19 09:10)
- **Requested by user:** (1) merge-message editors were not covered: under a real PTY, raw `pull --no-rebase --edit` succeeded, while the gateway's capture left the editor with no terminal, the pull failed and `MERGE_HEAD` was left. (2) `_ait_git_pull_cli_rebase_mode` did not consume the separate values of long options: in `pull --rebase=interactive --server-option --rebase`, git takes the second `--rebase` as the server-option value, but the scanner read it as an override, so the gateway fetched and opened the sequence editor (`--strategy-option --rebase` likewise).
- **Changes made:**
  - The scanner is rewritten as one walker, `_ait_git_pull_scan_args`, which resolves every token as git 2.56 does against git pull's own option table (`git pull -h`). Via `_ait_git_pull_resolve_long`, an exact name beats a prefix, a unique prefix resolves, and an ambiguous or unknown token resolves to nothing (git refuses the pull then; probed that `--strat` is "ambiguous option" and `--e` means `--edit`). Required-value long options (cleanup, deepen, depth, negotiation-*, refmap, server-option, shallow-*, strategy, strategy-option, upload-pack) consume the next token unless given as `=value`. Short clusters work as before. The walker also returns the last `--[no-]autostash` and `--[no-]edit` with their tokens, so the autostash check no longer has its own loop. `_ait_git_pull_cli_rebase_mode` is now a thin reader.
  - Editor policy: **no editor ever opens.** `--no-edit` is inserted after `pull` next to `--no-autostash` (probed: it beats `GIT_MERGE_AUTOEDIT=yes` and the tty default), and a user `--edit` (last-wins, any accepted abbreviation) is refused before anything runs. A merge commit takes git's default message.
  - Docs: a "No editor opens" bullet in `sync.md`.
- **Tests:** Test 18 gained value-consumption rows (`--server-option`/`--strategy-option`/`--server`/`-o`/`--upload-pack` before `--rebase`, plus an attached `--server-option=x` that does not consume), edit/autostash last-wins rows, and resolver rows. Gateway Test H adds three refusals where a value-consumed `--rebase` must not override (the editor never ran, nothing was fetched). New Test K runs under a real PTY: the control is plain git opening the editor; `--edit`, `--ed` and `--no-edit --edit` are refused before any fetch; and an accepted `--no-rebase` pull with `GIT_MERGE_AUTOEDIT=yes` completes as a 2-parent merge with no editor and no MERGE_HEAD. Mutants M9 (no value consumption), M10 (no `--no-edit`) and M11 (no `--edit` refusal) are all caught.
- **Files affected:** `.aitask-scripts/lib/task_utils.sh`, `tests/test_task_git.sh`, `tests/test_ait_git_gateway_pull.sh`, `website/content/docs/commands/sync.md`

### Change Request 3 (2026-10-19 10:05)
- **Requested by user:** (1) A merge-mode gateway pull stopped by a refusing `pre-merge-commit` hook leaves `MERGE_HEAD`, but `_task_pull_rebase_cleanup`'s Signal 3 (a non-conflict failure) printed rebase wording before Signal 4 identified the operation, so the gateway reported `rebase_in_progress` and gave rebase advice. (2) Test K's plain-git control had already fetched, so its "nothing was fetched" assertion could not detect a fetch-then-refuse. The reviewer showed this with a fixture-only mutation that passed all 149 assertions.
- **Changes made:** Signal 3 now words its message from the actual state: `rebase-*` keeps the "a rebase appeared … failed for another reason" line, and any other state gets "the data worktree is mid-<state>; leaving it untouched" (→ `data_midop`). Ownership protections are unchanged, and the state is still never touched. Test K advances the remote again after the control, before it records the tracking ref. The docs bullet now covers merges stopped by a hook as well as by a conflict.
- **Tests:** Test 46m (unit; MERGE_HEAD plus non-conflict output → `mid-MERGE_HEAD`, `data_midop`, no "rebase", and a hint with no rebase recovery). Gateway Test L (a real refusing `pre-merge-commit` hook → MERGE_HEAD left, `data_midop`, `--abort` merge hint, no rebase wording in our lines). Mutant M12 (Signal 3 reverted) fails 46m and L. Mutant M13 (the reviewer's fetch-before-refusing-`--edit`) now fails Test K's three "nothing was fetched" assertions.
- **Files affected:** `.aitask-scripts/lib/task_utils.sh`, `tests/test_task_push.sh`, `tests/test_ait_git_gateway_pull.sh`, `website/content/docs/commands/sync.md`

## Final Implementation Notes
- **Actual work done:**
  - `lib/task_utils.sh`:
    - One global-option walker, `_ait_git_scan_globals`, with the readers `ait_git_subcmd_index` / `ait_git_redirect_opt`.
    - `assert_data_worktree_clean` classifies from the parsed subcommand (guarded `set --` slice; `${@:0}` avoided).
    - `_task_pull_rebase` is a thin wrapper over the new `_ait_owned_pull`, the single copy of the five-signal ownership pipeline. While still holding the pull mutex, the core checks that a pull ending in rc 0 left no in-progress state and no unmerged path, and that the check itself ran. Each failure carries `AIT_PULL_UNVERIFIED_SENTINEL`, which `_task_push_classify` (second arm, ahead of conflict text → `unknown`), `task_sync` (warned regardless of counts) and `task_push` (warned on both exits) recognize.
    - The new `task_git_gateway` refuses `-C`/`--git-dir`/`--work-tree`/`--namespace` and routes `pull` to `task_git_pull`. `task_git_pull` forces `--no-autostash --no-edit`; refuses user `--autostash` and `--edit`, and interactive rebase from arguments or config (`branch.<cur>.rebase` > `pull.rebase`, read with the user's `-c`); and prepends the user's `-c`/`--config-env` to a function-local `AIT_RECONCILE_GIT_OPTS`, framework pins last, so the continue and the abort carry it.
    - `_ait_git_pull_scan_args` resolves the pull's own arguments against git pull's option table: last wins, unique-prefix abbreviations, required-value options consume the next token, short clusters.
    - Signal 3 of `_task_pull_rebase_cleanup` names the actual state.
  - `ait`: the git arm calls `task_git_gateway`.
  - Docs: `## ait git pull` in `commands/sync.md`, a global-options note, and a row in the commands index.
  - Tests: `test_task_git.sh` Tests 17 (pre-phase characterization), 18 (parser/scan/mode/resolver tables) and 19 (the paired recovery regression); `test_task_push.sh` Test 46m and Test 64 (J0–J7 plus a classifier unit); new `test_ait_git_gateway_pull.sh` (A, A2, B–L incl. H, K, I) through the real dispatcher in branch mode.
- **Deviations from plan:**
  - Bare `--exec-path` takes no value (it follows git, probed), not the task's list.
  - The gateway pull's output moved to stderr.
  - Review rounds added: the autostash refusal and the user-config carry (plan revisions before approval); the completion postcondition under the mutex, with explicit caller recognition (plan revisions); then CR1 (interactive refusal and paused-state postcondition), CR2 (editor policy and the option-table scanner) and CR3 (Signal 3 state wording, Test K fetch proof).
- **Issues encountered:**
  - Every reviewer finding reproduced and was fixed.
  - Pre-phase evidence: on the unmodified library, Test 17 was green and Test 19 failed only on `-c core.pager=cat rebase --abort is ALLOWED (got 'refused')`.
  - Mutation checks M1–M13 (config carry, `--no-autostash`, gateway routing, classifier precedence, sync zero-pending warn, check-under-mutex, interactive refusal, paused-state check, long-option value consumption, `--no-edit`, `--edit` refusal, Signal 3 wording, fetch-before-refuse) were each caught by their targeted assertions.
- **Key decisions:**
  - Refuse rather than emulate: interactive rebase, `--edit` and `--autostash` all need a terminal, or the shared worktree, in ways a captured, cleanup-owning gateway cannot honour.
  - The reason vocabulary is unchanged (the sentinel maps to `unknown` with its line as the detail).
  - Merge-mode cleanup is left as an explicit bound (the after-mitigation `gateway_merge_pull_cleanup`).
  - `push` still keys on `$1` (the after-mitigation `gateway_push_global_opts`).
- **Upstream defects identified:**
  - `tests/test_aitask_merge_boardgroup.sh:200-205` — Test 3 greps `aitask_sync.sh` for `"$_MERGE_PYTHON" "$_MERGE_SCRIPT"` driver invocations, but the driver call moved to `lib/task_automerge.sh`, so "At least one driver invocation exists" fails on main independent of this task.
  - `tests/test_no_unscoped_task_commit.sh:679-680` — the scope assertion "markdown: the canonical teaching skill is in scope" (`.claude/skills/ait-git/SKILL.md` in the enumerated markdown sources) fails independent of this task; the root cause was not investigated.
