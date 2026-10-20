---
Task: t2070_sync_converge_remote_probe_failure_silent.md
Base branch: main
Output branch: main
---

# t2070 — a failed `git remote` probe must not read as "no remote" in sync / converge

## Context

t2063 fixed `task_push`: a `git remote` query that **fails** (git cannot read its
configuration → exit 128 on every command) used to be read as an empty remote
list, so a push with commits pending reported `NO_REMOTE`, exited 0 and printed
nothing. Two more callers of the same probe still behave the old way:

- `lib/task_utils.sh::task_sync` (`:1187`) → `TASK_SYNC_STATUS=no-remote`, silent
  (this is the pre-pick pull run by `aitask_pick_own.sh --sync`).
- `lib/task_utils.sh::task_data_converge` (`:2156`) → `TASK_CONVERGE_STATUS=no-remote`, silent.

Both gate on `_task_push_has_remote`, which runs `git remote 2>/dev/null || true`.

The task also asks what the `ait sync --batch` vocabulary should print. Measured
on a `tests/lib/sync_fixture.sh` branch-mode repo with `[core` appended to
`.git/config`: **`aitask_sync.sh --batch` prints `NO_REMOTE`, exits 0, stderr
empty.** `aitask_sync.sh::check_remote` (`:352`) runs
`task_git remote get-url origin &>/dev/null` and reads any failure as "no
origin". That is the same defect in a third place, and it is the command the
sync/converge warning hints send the user to (`reconcile with './ait sync'`), so
it is in scope. Probed git behaviour (git in this box): broken config →
`git remote` / `git remote get-url origin` both exit 128 with
`fatal: bad config line N in file .git/config`; a genuinely remote-less repo →
`git remote` exits 0 with empty stdout, `get-url origin` exits 2.

## Implementation

### 1. `lib/task_utils.sh` — one shared remote probe

Replace `_task_push_has_remote` (its last two callers go away; no other
references in `.aitask-scripts/` or `tests/`) with a probe that keeps the status,
factored out of the inline block t2063 put in `task_push`:

```bash
# Internal: query the configured remotes ONCE (t2063, t2070). A query that
# FAILED is not an empty remote list: git refuses every command when it cannot
# read its configuration, and reading that refusal as "no remote" skipped the
# pending reconcile in silence. Sets _TASK_REMOTE_LIST to `git remote`'s stdout.
# On failure returns 1 and sets _TASK_REMOTE_DETAIL to " (git: <first line>)";
# only a failed query runs again, for its stderr — a configuration error is
# deterministic, so the rerun says what the first one hit.
_TASK_REMOTE_LIST=""
_TASK_REMOTE_DETAIL=""
_task_remote_probe() {
    local rc=0 err=""
    _TASK_REMOTE_LIST=""
    _TASK_REMOTE_DETAIL=""
    _TASK_REMOTE_LIST="$(_task_push_git remote 2>/dev/null)" || rc=$?
    [[ $rc -eq 0 ]] && return 0
    err="$(_task_push_git remote 2>&1 >/dev/null || true)"
    err="$(_task_push_first_line "$err")"
    _TASK_REMOTE_DETAIL=" (git: ${err:-'git remote' exited ${rc}})"
    return 1
}
```

Callers use it as `if ! _task_remote_probe; then` (errexit-safe under
`aitask_pick_own.sh`'s `set -euo pipefail`). It stays on `_task_push_git`, so
`task_push` keeps carrying the user's `-c` options (t2063) and the other two run
with the empty default, exactly as today.

- **`task_push`** — replace the inline `remote_list/remote_err/remote_rc` block
  with the helper. Labels unchanged: `failed` / `unknown` / unpushed count /
  `_task_push_warn "$_TASK_REMOTE_DETAIL"`; empty `_TASK_REMOTE_LIST` →
  `no-remote`. Behaviour-preserving; Test P5 in `tests/test_ait_git_gateway_pull.sh`
  pins it.
- **`task_sync`** — on probe failure: `TASK_SYNC_STATUS=failed`,
  `TASK_SYNC_REASON=unknown`, sample `TASK_SYNC_UNPUSHED` / `TASK_SYNC_UNPULLED`
  with the existing probes, `_task_sync_warn "$_TASK_REMOTE_DETAIL" ""`, return 0.
  Empty list → `no-remote` (silent) as now. With a broken config both counts are
  `""`, so `_task_sync_warn` takes its "counts unavailable" branch, which always
  warns; reason `unknown` gets the `./ait git-health` hint. `aitask_pick_own.sh
  --sync` therefore prints `SYNC_FAILED:unknown` (existing vocabulary, same
  reason code `task_push` uses → `FAILED:unknown:…`). No new reason code.
- **`task_data_converge`** — on probe failure: `TASK_CONVERGE_STATUS=failed`,
  `TASK_CONVERGE_REASON=unknown`, sample `AHEAD` / `BEHIND`, warn, return 0.
  `_task_converge_warn` has no detail slot, so add an optional `$2 = detail`
  appended before the context (`— ${hint}${detail}${context}`) on both of its
  `warn` lines; existing callers pass nothing and are unchanged.
- Update the `AIT_PUSH_GIT_OPTS` comment, which names the probes as shared.

### 2. `aitask_sync.sh::check_remote` — disambiguate a failed lookup

```bash
check_remote() {
    task_git remote get-url origin &>/dev/null && return 0
    # A failed lookup means "no origin" only when git could read its
    # configuration (t2070): an unreadable config fails every command, and
    # reading that as NO_REMOTE skipped the sync in silence. Only the failure
    # path asks again, with the plain remote list, whose status separates the two.
    local err="" rc=0
    err="$(task_git remote 2>&1 >/dev/null)" || rc=$?
    if [[ $rc -ne 0 ]]; then
        batch_out "ERROR:remote_probe_failed"
        warn "Could not read the git configuration; nothing was synced (git: ${err%%$'\n'*})"
        exit 1
    fi
    batch_out "NO_REMOTE"
    ...unchanged...
}
```

`ERROR:<code>` + exit 1 is the shape `_refuse_unresolved_gitdir` already uses;
`sync_action_runner.parse_sync_output` maps any `ERROR:` line to `STATUS_ERROR`
and `run_sync_batch` parses stdout regardless of exit status, so both TUIs show
it as an error rather than a benign "no remote". `warn` (not `iwarn`) so batch
callers' stderr carries git's line too. Add the token to the header comment
list only if it enumerates codes (it does not — `ERROR:<message>` covers it).

### 3. Docs

- `website/content/docs/commands/sync.md`:
  - "How It Works" step 2: add that a configuration git cannot read is reported
    as `ERROR:remote_probe_failed` (git's message on stderr) and nothing is synced.
  - The push and pre-pick pull "stays quiet … no remote configured" paragraphs:
    one sentence each that a repository whose git configuration cannot be read
    is not treated as having no remote — it is reported as a failed push/pull
    with git's message.
  - Run `python3 check_links.py --build` (in `website/`).
- `aidocs/framework/failopen_git_probes.md` "Deliberately left alone" row: drop
  `::_task_push_has_remote:1388` (the function no longer exists; its replacement
  keeps the status).

### 4. Tests

`tests/test_task_push.sh` (new Test 65, before `# --- Summary ---`), fixture =
`setup_remote_and_clone` + one local commit, then `echo '[core' >> .git/config`:

- precondition: `git remote` exits non-zero in the fixture (proves the fixture
  is broken the right way);
- `task_sync`: rc 0, `TASK_SYNC_STATUS=failed`, `REASON=unknown`, stderr contains
  `bad config line` and `sync failed`, not `no-remote`;
- `task_data_converge "test"`: rc 0, `failed` / `unknown`, stderr contains
  `bad config line` and `not converged`;
- `task_push`: still `failed` / `unknown` via the shared helper (in-process
  companion to P5);
- `aitask_pick_own.sh --sync` (reuse `setup_pick_own_cli` from Test 23) prints
  `SYNC_FAILED:unknown`;
- **control**: a `git remote remove origin` repo (Test 13 shape) — `task_sync` →
  `no-remote`, stderr empty (Test 33 already covers converge's control).
- **mutant check (manual, not committed)**: temporarily restore
  `_task_push_has_remote` gating in `task_sync` on a scratch copy and confirm
  the new assertions go red.

`tests/test_sync_failopen_probes.sh` (new section before `# --- Summary ---`),
using `setup_repo` from `tests/lib/sync_fixture.sh`:

- broken config → stdout `ERROR:remote_probe_failed`, rc 1, stderr contains
  `bad config line`, remote `aitask-data` sha unchanged;
- control: `git -C local remote remove origin` → `NO_REMOTE`, rc 0.

## Verification

```bash
bash tests/test_task_push.sh
bash tests/test_ait_git_gateway_pull.sh          # P5 still green after the refactor
bash tests/test_sync_failopen_probes.sh
bash tests/test_metadata_partial_sync_recovery.sh  # converge consumer
shellcheck .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_sync.sh
(cd website && python3 check_links.py --build)
```

Step 9 (Post-Implementation): current-branch mode — commit code and plan
separately, archive via the standard flow.

## Risk

### Code-health risk: low
None identified. (Three small call sites in two files. The one behaviour-preserving
refactor, moving `task_push`'s probe into the shared helper, is already pinned by
P5 and by the in-process Test 65 assertion, both part of this plan.)

### Goal-achievement risk: low
None identified.

## Post-review changes

### Change request 1 (2026-10-20)
- **Requested by user:** the new `sync.md` step-2 sentence promised
  `ERROR:remote_probe_failed` + git's diagnostic whenever the repo config is
  unreadable, which is false from a linked checkout (reviewer reproduced
  `ERROR:data_gitdir_unresolved` there). Qualify the doc; keep the earlier guard;
  no runtime change.
- **Verified:** reproduced primary + linked checkout sharing a broken config,
  plus a legacy-mode repo. Primary → `ERROR:remote_probe_failed` (git line on
  stderr). Linked → `ERROR:data_gitdir_unresolved` (`_ait_data_gitdir`'s
  `git rev-parse --absolute-git-dir` fallback fails first; stderr carries no git
  line). Legacy → also `ERROR:data_gitdir_unresolved` (`_data_wedge_gitdir` runs
  `git rev-parse --git-dir`). `aitask_pick_own.sh --sync` and
  `./ait git push --batch` report `SYNC_FAILED:unknown` / `FAILED:unknown:unknown`
  with git's line from BOTH checkouts, so those two doc sentences stand.
- **Changes made:** `sync.md` step 2 now scopes the token to "when this check
  runs", names the only layout that reaches it with an unreadable config
  (primary checkout, `aitask-data` branch mode), and documents the earlier
  `ERROR:data_gitdir_unresolved` stop for linked checkouts and legacy layouts,
  telling the user to run any git command (e.g. `git status`) to see git's
  message, since that refusal's stderr does not carry it.
- **Files affected:** `website/content/docs/commands/sync.md`

## Final Implementation Notes
- **Actual work done:** as planned. `_task_remote_probe` (lib/task_utils.sh)
  replaces `_task_push_has_remote`; `task_push` (refactored, labels unchanged),
  `task_sync` and `task_data_converge` report `failed` / `unknown` with
  " (git: <first line>)" on a failed probe. `_task_converge_warn` gained an
  optional `$2` detail slot. `aitask_sync.sh::check_remote` re-asks with
  `git remote` only when `get-url origin` fails; a failed list →
  `ERROR:remote_probe_failed`, exit 1, `warn` with git's line. Docs: `sync.md`
  (step 2 + the push/pull "stays quiet" paragraphs), `failopen_git_probes.md`
  (dropped the deleted helper from the left-alone row; added the two fixed sites
  to the fix-shape table, "Four sites" → "These sites"). Tests: Test 65 in
  `tests/test_task_push.sh`, section R in `tests/test_sync_failopen_probes.sh`.
- **Deviations from plan:** `failopen_git_probes.md` also gained the two
  fix-shape rows (plan only said drop the row entry). Doc wording for step 2
  qualified after review (see Post-review changes).
- **Issues encountered:** none in code. Mutants (applied to an isolated scratch
  copy of the tree, never the shared worktree): ignoring the probe failure in
  task_sync/converge → 11 Test 65 assertions red (old `no-remote` / `SYNCED`);
  `if false` in check_remote → 3 R-1 assertions red (`NO_REMOTE`, exit 0).
- **Key decisions:** reuse reason `unknown` (no new classifier code) so
  `SYNC_FAILED:unknown` / `FAILED:unknown:…` stay in the existing vocabulary;
  `ERROR:remote_probe_failed` + exit 1 mirrors `ERROR:data_gitdir_unresolved`.
  `_task_sync_warn`'s "counts unavailable" branch always warns, so a broken
  config is never silent even with the zero-pending quiet policy.
- **Upstream defects identified:** None
- **Verification:** test_task_push 461/461, test_sync_failopen_probes 58/58,
  test_ait_git_gateway_pull 209/209 (P5), test_metadata_partial_sync_recovery
  38/38, `check_links.py --build` PASSED; shellcheck: pre-existing findings only.
