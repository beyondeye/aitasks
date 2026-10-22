---
Task: t2127_verify_setup_data_branch_single_branch_clone.md
Base branch: main
Output branch: main
---

# t2127 — data-branch bootstrap in a `--single-branch` clone

## Context

t2099 found that a `git clone --single-branch -b main` clone's only fetch
mapping for origin is `+refs/heads/main:refs/remotes/origin/main`. Two git
facts follow, and the data-branch bootstrap (`setup_data_branch` in
`.aitask-scripts/aitask_setup.sh:1585`, `aitask_init_data.sh` Check 3/Step 4)
handles neither:

1. **Download.** `git fetch origin aitask-data` (setup.sh:1713, init_data.sh:205)
   writes only `FETCH_HEAD`, so `refs/remotes/origin/aitask-data` never appears
   and the DWIM `git worktree add .aitask-data aitask-data` fails ("invalid
   reference") → setup drops to the legacy layout, init_data dies.
2. **Upstream resolution.** git resolves `aitask-data@{u}` by mapping
   `branch.aitask-data.merge` **through origin's fetch refspecs**. With no
   mapping, `@{u}` is unresolvable even when the branch config and the tracking
   ref both exist — and `ait sync` pins `@{u}` (`aitask_sync.sh:1750, 2154`).

Fact 2 hits **every** route, not only the fetch route (confirmed during plan
review in temporary single-branch clones):
- **create route** — remote has no `aitask-data`; setup creates it and
  `push -u` succeeds, but `@{u}` stays unresolvable (no mapping, and the push
  created no tracking ref);
- **local-branch route** — init_data finds an existing local branch (e.g. the
  t2099 fixture's hand-configured `remote`/`merge`) → `INITIALIZED`, `@{u}`
  unresolvable;
- **fetch route** — fact 1 and fact 2 together.

`ait sync` itself already downloads the branch with an explicit refspec
(`aitask_sync.sh:1989`), so it is fine once the mapping and upstream exist.

**Approach:** split the two concerns.
- *Download* = an explicit-refspec fetch (network), used only where a download
  is wanted.
- *Normalization* = a **network-free** reconcile of the mapping and the
  upstream, run after the worktree exists on **every** route (fetch, create,
  local branch, and setup's "already configured" re-run, which is the repair
  path). It writes the mapping only when the upstream is, or is about to be,
  `origin/aitask-data`; it never touches an upstream someone configured
  elsewhere; and when nothing has ever been fetched or published (offline,
  unreachable remote) it does nothing.
- The local branch is created **explicitly** from the tracking ref instead of
  relying on the `worktree add` DWIM, which needs the mapping first.

Plain clones: the `refs/heads/*` glob already maps `aitask-data`, so their
fetch config is never changed; the end state (branch tracks
`origin/aitask-data`) matches what DWIM gave them before.

Current-branch mode (profile `fast`): no worktree.

## Step 1 — Red proof first

Write the tests from Step 4 and run them against the unmodified scripts.
Record each failure (worktree-add error, `@{u}` result, init_data output) for
the Final Implementation Notes. The plain-clone control (Test 39) and the
preservation/offline tests must pass both before and after.

## Step 2 — Shared helpers in `.aitask-scripts/lib/data_symlinks.sh`

Both scripts already source this lib (setup.sh:27, init_data.sh:48); it is the
home of the shared data-layout helpers. Add the functions below, and name them
in the lib's header comment.

```bash
_AIT_DATA_SPEC="+refs/heads/aitask-data:refs/remotes/origin/aitask-data"

# ait_fetch_data_branch <repo_dir> -- DOWNLOAD only: fetch origin's aitask-data
# into refs/remotes/origin/aitask-data with an explicit refspec. A bare
# `git fetch origin aitask-data` lands in FETCH_HEAD alone in a --single-branch
# clone (t2127). Writes no config. On failure git's message is in
# AIT_DATA_FETCH_ERR.
ait_fetch_data_branch() {
    AIT_DATA_FETCH_ERR=""
    AIT_DATA_FETCH_ERR="$(git -C "$1" fetch origin "$_AIT_DATA_SPEC" 2>&1 >/dev/null)"
}

# ait_ensure_local_data_branch <repo_dir> -- create a local aitask-data from
# origin/aitask-data when only the tracking ref exists. Replaces the
# `git worktree add` DWIM, which cannot find a tracking branch its remote's
# fetch config does not map. The upstream is set by the reconcile below.
ait_ensure_local_data_branch() {
    git -C "$1" show-ref --verify -q refs/heads/aitask-data && return 0
    git -C "$1" show-ref --verify -q refs/remotes/origin/aitask-data || return 0
    git -C "$1" branch -q --no-track aitask-data refs/remotes/origin/aitask-data
}

# _ait_data_branch_mapped <repo_dir> -- origin's fetch config maps aitask-data.
_ait_data_branch_mapped() {
    local v
    while IFS= read -r v; do
        case "${v#+}" in
            "refs/heads/*:refs/remotes/origin/*"|"${_AIT_DATA_SPEC#+}") return 0 ;;
        esac
    done < <(git -C "$1" config --get-all remote.origin.fetch 2>/dev/null)
    return 1
}

# ait_reconcile_data_branch_upstream <repo_dir> -- NETWORK-FREE normalization
# so aitask-data@{u} resolves to origin/aitask-data (ait sync pins @{u}; git
# maps the upstream through origin's fetch refspecs, so a --single-branch
# clone needs aitask-data mapped -- t2127). Leaves alone: a repo with no origin
# or no local aitask-data; an upstream configured to anything other than
# origin/aitask-data; and a branch that was never fetched or published.
# Returns 0 resolved / nothing to do, 1 a write failed or @{u} still does not
# resolve (AIT_DATA_UPSTREAM_ERR), 2 upstream is origin/aitask-data but its
# tracking ref has not been fetched yet.
ait_reconcile_data_branch_upstream() {
    local dir="$1" remote merge
    AIT_DATA_UPSTREAM_ERR=""
    git -C "$dir" remote get-url origin >/dev/null 2>&1 || return 0
    git -C "$dir" show-ref --verify -q refs/heads/aitask-data || return 0
    remote="$(git -C "$dir" config --get branch.aitask-data.remote 2>/dev/null)" || remote=""
    merge="$(git -C "$dir" config --get branch.aitask-data.merge 2>/dev/null)" || merge=""
    if [[ -n "$remote$merge" ]]; then
        [[ "$remote" == origin && "$merge" == refs/heads/aitask-data ]] || return 0
    elif ! git -C "$dir" show-ref --verify -q refs/remotes/origin/aitask-data; then
        return 0
    fi
    if ! _ait_data_branch_mapped "$dir"; then
        if ! AIT_DATA_UPSTREAM_ERR="$(git -C "$dir" config --add remote.origin.fetch "$_AIT_DATA_SPEC" 2>&1)"; then
            AIT_DATA_UPSTREAM_ERR="could not add $_AIT_DATA_SPEC to remote.origin.fetch: ${AIT_DATA_UPSTREAM_ERR:-<no output>}"
            return 1
        fi
    fi
    git -C "$dir" show-ref --verify -q refs/remotes/origin/aitask-data || return 2
    if [[ -z "$merge" ]]; then
        AIT_DATA_UPSTREAM_ERR="$(git -C "$dir" branch -q --set-upstream-to=origin/aitask-data aitask-data 2>&1)" || return 1
    fi
    git -C "$dir" rev-parse --verify -q 'aitask-data@{u}' >/dev/null \
        || { AIT_DATA_UPSTREAM_ERR="aitask-data@{u} still does not resolve"; return 1; }
}

# ait_report_data_branch_upstream <repo_dir> -- run the reconcile and report on
# stderr; never fails the caller (the layout is usable without an upstream).
ait_report_data_branch_upstream() {
    local rc=0
    ait_reconcile_data_branch_upstream "$1" || rc=$?
    case "$rc" in
        1) warn "Could not make origin/aitask-data the aitask-data branch's upstream ('ait sync' needs it): ${AIT_DATA_UPSTREAM_ERR:-<no output>}" ;;
        2) info "  aitask-data's upstream origin/aitask-data is not fetched yet; the next 'ait sync' fetches it." >&2 ;;
    esac
    return 0
}
```

Every `$( )` sits in an `||` / `if` context (errexit-safe). The mapping is
written only when the remote demonstrably carries the branch (a tracking ref
exists, or the upstream already names it), so an offline or unpublished branch
gets no refspec — an exact refspec whose source branch is missing would make
every later `git fetch origin` fail.

## Step 3 — Wire every route

**`aitask_setup.sh` `setup_data_branch`:**
- **Already-configured early return** (line ~1594): call
  `ait_report_data_branch_upstream "$project_dir"` before `return` — `ait setup`
  is the repair verb, and this is how an existing broken single-branch install
  gets fixed. Network-free and idempotent.
- **Fetch route** (Step 1, ~1713): replace the inline fetch with
  `if ait_fetch_data_branch "$project_dir"; then branch_exists=true; else warn "Could not fetch the aitask-data branch from remote. git said: ${AIT_DATA_FETCH_ERR:-<no output>}"; fi`.
  The local-fallback and "present but unfetchable" refusal below stay as they are.
- **Create route** (~1756): after a **successful** `push -u`, run
  `ait_fetch_data_branch "$project_dir" || warn "Pushed aitask-data but could not fetch it back, so 'ait sync' has no upstream yet. git said: ${AIT_DATA_FETCH_ERR:-<no output>}"`
  so the tracking ref exists (the push made none without a mapping). A failed
  push changes nothing (offline behaviour preserved).
- **Before Step 2's `git worktree add`:** `ait_ensure_local_data_branch "$project_dir"`
  (on failure take the existing worktree-failure path: warn and `return`).
- **After Step 2 succeeds:** `ait_report_data_branch_upstream "$project_dir"`.

**`aitask_init_data.sh`:**
- Check 3 fetch (~205) through `ait_fetch_data_branch "$PWD"`, keeping its
  warn and `NO_DATA_BRANCH` exit, now with `AIT_DATA_FETCH_ERR`.
- Before Step 4's `git worktree add`: `ait_ensure_local_data_branch "$PWD"`
  (failure → the existing `die` with git's message).
- After Step 4: `ait_report_data_branch_upstream "$PWD"` — stderr only;
  stdout keeps carrying just the token. This covers the local-branch route
  with a hand-configured upstream.
- `ALREADY_INIT` is left unchanged: repair belongs to `ait setup`.

## Step 4 — Tests

**`tests/test_data_branch_setup.sh`**, appended before the summary in the
Test 23–25 fixture style (`setup_repo_with_remote`, `seed_remote_data_branch`,
`SCRIPT_DIR=<clone>/.aitask-scripts`, Test 1's seed copy). Single-branch
clones use `git clone -q --single-branch -b <default> "file://$T/remote.git"`.
A shared `assert_data_upstream <label> <repo>` checks
`git rev-parse --symbolic-full-name aitask-data@{u}` =
`refs/remotes/origin/aitask-data`.

- **38 fetch route:** the remote carries `aitask-data` and a `store-x` branch.
  Run `setup_data_branch` → `.aitask-data` is a worktree on `aitask-data`,
  `aitasks` is a symlink, the upstream resolves, `remote.origin.fetch` holds the
  explicit refspec exactly once, and `refs/remotes/origin/store-x` is absent
  even after a plain `git fetch origin`.
- **38b create route:** the remote has no `aitask-data` → setup creates and
  pushes it → the upstream resolves and the tracking ref equals the local branch.
- **38c repair on re-run:** a t2099-shaped hand-built layout (explicit fetch,
  `branch --no-track`, manual `remote`/`merge`, `worktree add`, no mapping) →
  the upstream does not resolve (precondition) → `setup_data_branch` (the
  already-configured return) → it resolves.
- **38d preservation:** a local `aitask-data` whose upstream is a second remote
  `other` → after setup, `branch.aitask-data.{remote,merge}` and
  `remote.origin.fetch` are byte-identical to before.
- **38e offline:** a single-branch clone whose origin URL is unreachable
  (Test 25 shape) → the worktree is still created, `remote.origin.fetch` is
  unchanged, and there is no upstream warning.
- **38f idempotence:** a second reconcile on 38's clone leaves exactly one copy
  of the refspec.
- **39 plain-clone control:** normal clone, remote carries `aitask-data` →
  `remote.origin.fetch` unchanged (only the glob) and the upstream resolves.
- Test 23's fetch shim matches any `fetch`, so it keeps covering the failure path.

**`tests/test_init_data.sh`:**
- **5b** — the single-branch twin of Test 5 → `INITIALIZED`, upstream resolves.
- **5c** — local-branch route: a single-branch clone with a local `aitask-data`
  carrying the hand-configured `remote`/`merge` and an explicitly fetched
  tracking ref → `INITIALIZED` and the upstream resolves (red before the fix).
(`setup_fake_aitask_repo` already copies `lib/data_symlinks.sh` —
`tests/lib/test_scaffold.sh:87`.)

**`tests/test_sync_fetch_exclusion.sh` scenario 2** (the t2099 hand-built
layout): its `ait sync` ran with an unresolvable `@{u}`, so the "no store
objects" assertions held without a real pull. Build the layout through
`setup_data_branch` (or add the mapping as setup now does), and assert that
sync's verdict line is a success.

## Verification

```bash
bash tests/test_data_branch_setup.sh
bash tests/test_init_data.sh
bash tests/test_data_branch_migration.sh
bash tests/test_sync_fetch_exclusion.sh
bash tests/test_ait_git_gateway_pull.sh
bash tests/test_setup_git.sh
bash tests/test_install_create_data_dirs.sh
bash tests/test_applink_setup_gitignore.sh
shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/aitask_init_data.sh .aitask-scripts/lib/data_symlinks.sh
```

Tests 38, 38b, 38c, 5b and 5c must fail on the pre-fix code and pass after;
38d, 38e and 39 pass both before and after.

## Step 9 (Post-Implementation)

Commit code and tests as `bug: ... (t2127)` with an explicit pathspec (other
sessions have unrelated dirty files in this checkout), then archive per the
workflow's Step 9.

## Risk

### Code-health risk: low
- `setup_data_branch` is on the install flow, and replacing the DWIM with an explicit branch create plus reconcile changes how plain clones get their upstream. The end state is the same (`origin/aitask-data` tracked), and the Test 39 control plus existing Tests 1, 23–25 pin it · severity: low · → mitigation: covered in-plan (Test 39, existing Tests 1/23–25)
- A persisted exact refspec makes `git fetch origin` fail if `aitask-data` is later deleted on the remote. It is written only once the remote demonstrably carries the branch, and a deleted data branch already breaks `ait sync` · severity: low · → mitigation: covered in-plan (write rule in Step 2, 38e)

### Goal-achievement risk: low
- Bypass routes (create, local branch, re-run) were the gap found in review; every route now ends in the same reconcile, and each has a red-before/green-after test · severity: low · → mitigation: covered in-plan (Tests 38–38c, 5b, 5c)
