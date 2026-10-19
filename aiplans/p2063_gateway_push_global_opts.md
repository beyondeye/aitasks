---
Task: t2063_gateway_push_global_opts.md
Base branch: main
Output branch: main
---

# t2063 — `./ait git <global-opts> push` goes through the best-effort push

## Context

`ait` routes `git push` on `$1` (`ait:345-358`). `./ait git push` therefore reaches
`task_push` (retries, a pull-rebase between attempts, reason classification,
`--batch` reporting), while `./ait git -c x push` falls to `task_git_gateway` →
`task_git` and runs a raw `git push`. That skips the whole best-effort contract.
t1739 left this as an explicit bound (its `## Risk`, mitigation `t2063`).

**Decision: route, don't refuse.** The parser (`_ait_git_scan_globals`) and the
config-carrying mechanism (`task_git_pull`'s function-local
`AIT_RECONCILE_GIT_OPTS` override) already exist, and the plausible reason to put
`-c` in front of a push is network config (`core.sshCommand`, `http.proxy`,
`url.*.insteadOf`) — which the retry pull needs just as much as the push. So:

- `-c` / `--config-env` reach **every push attempt, the retry pull, and the
  pull's cleanup (auto-merge continue / abort)**;
- any **other** global option in front of `push` (`--no-pager`, `-p`, `--bare`, …)
  is **refused** — threading it through every attempt is not worth a contract,
  and carrying it to some calls only would be the same half-contract this task
  closes. Redirect options (`-C`, `--git-dir`, …) stay refused by the existing
  gateway check, which now runs first for push too.
- Arguments after `push` behave exactly as in the bare form: `--batch` is
  recognised, everything else is ignored.

## Steps

### 1. `.aitask-scripts/lib/task_utils.sh`

- Next to `AIT_RECONCILE_GIT_OPTS=(…)` (~:1617) add a global
  `AIT_PUSH_GIT_OPTS=()` with a comment: the options every git call of the
  **push cycle** carries — the remote / upstream / unpushed probes as well as
  each push attempt — so the preflight and the report describe the same
  configuration the upload uses; empty by default; ONE sanctioned override —
  `task_git_push` re-declares it function-locally; read at call time.
- New internal `_task_push_git() { _ait_data_git ${AIT_PUSH_GIT_OPTS[@]+"${AIT_PUSH_GIT_OPTS[@]}"} "$@"; }`,
  and route the push-cycle helpers through it:
  - `_task_push_once` (`push --quiet`);
  - `_task_push_has_remote` (`remote`) — **reviewer finding**: without it a
    remote supplied only via `-c remote.origin.url=…` is reported `NO_REMOTE`
    before any attempt;
  - `_task_push_unpushed_count` (`rev-list @{upstream}..HEAD`) and
    `_task_push_upstream` (`rev-parse @{upstream}`) — so a `-c branch.<b>.merge`
    / `-c remote.origin.fetch` upstream is the one the before/after counts and
    `_task_push_warn`'s "not pushed to <upstream>" line describe.
  These helpers are shared with `task_sync` / `task_data_converge`; there the
  array is empty, so their calls are byte-identical to today.
  (Not changed: `_ait_owned_pull`'s HEAD / unmerged-path probes, which no
  remote/branch config can alter; the pull itself already gets the user config
  through the local `AIT_RECONCILE_GIT_OPTS`.)
- New `task_git_push <git argv…>` (beside `task_git_gateway`):
  ```bash
  task_git_push() {
      _ait_git_scan_globals "$@"
      local idx="$AIT_GIT_SUBCMD_IDX"
      if (( ${#AIT_GIT_OTHER_OPTS[@]} )); then
          die "./ait git push: '${AIT_GIT_OTHER_OPTS[0]}' is not supported before 'push' - only -c and --config-env are carried into the best-effort push (every attempt and its retry pull). Drop it, or use plain 'git -C .aitask-data ${AIT_GIT_OTHER_OPTS[0]} push'."
      fi
      local push_batch=0 arg
      for arg in "${@:idx+1}"; do [[ "$arg" == "--batch" ]] && push_batch=1; done
      local -a framework_opts=("${AIT_RECONCILE_GIT_OPTS[@]}")
      local -a AIT_RECONCILE_GIT_OPTS=(${AIT_GIT_CONFIG_OPTS[@]+"${AIT_GIT_CONFIG_OPTS[@]}"} "${framework_opts[@]}")
      local -a AIT_PUSH_GIT_OPTS=(${AIT_GIT_CONFIG_OPTS[@]+"${AIT_GIT_CONFIG_OPTS[@]}"})
      task_push
      if (( push_batch )); then task_push_report; fi
      return 0
  }
  ```
  (The other-opts value is captured before `die`; `_ait_git_scan_globals` is
  called directly, never in `$( )`.)
- `task_git_gateway`: after the redirect refusal, dispatch `push` to
  `task_git_push "$@"` exactly like `pull`; update its header comment (no longer
  "everything except push"; routing for both is on the parsed argv).
- Update the AIT_RECONCILE_GIT_OPTS comment's "ONE sanctioned override" sentence
  to name both `task_git_pull` and `task_git_push`.

### 2. `ait` dispatcher

`git)` arm becomes `shift; source …/task_utils.sh; task_git_gateway "$@"` — the
`$1 == push` branch and its inline `--batch` loop move into `task_git_push`.
Bare `push` has no global options, so it passes the redirect check and lands in
`task_push` exactly as before (`tests/test_task_push.sh` Tests 8/15 pin it).

### 3. Tests — extend `tests/test_ait_git_gateway_pull.sh` (real dispatcher, branch-mode fixture)

Header comment: covers `pull` and `push`. Add a stdout-capturing runner
(`run_ait_out`: sets RC, OUT, ERR). New cases:

- **P1 bare vs option-prefixed, same outcome.** Fixture: `local_commit` +
  `remote_commit` (non-conflicting) so the first push is rejected non-ff and the
  retry pull rebases. Run `push --batch` → outcome tuple
  `rc|stdout token|remote contains local commit|unpushed count`. Second fresh
  fixture: `-c core.pager=cat push --batch` → equal tuple (computed, not
  hand-written). Also without `--batch`: `-c core.pager=cat push` exits 0 and the
  remote has the commit (pre-fix: raw push rejected non-ff, nonzero).
- **P2 config reaches push AND the retry pull.** Fixture with a local commit and a
  remote advance; repoint `origin` to a bogus `$FX/moved.git`.
  Control: bare `push --batch` → `FAILED:…`, remote unchanged.
  Then `-c url.<real>.insteadOf=<bogus> push --batch` → `PUSHED`, remote
  contains the local commit. Discriminator: config only on the push → the retry
  pull cannot fetch → still non-ff → `FAILED`; config only on the pull → push
  never reaches the remote. (Verify insteadOf rewrites a local path; else use
  `file://` URLs.)
- **P4 remote supplied only on the command line (reviewer regression).**
  Fixture: local commit + remote advance, then
  `git -C "$DATA" config --remove-section remote.origin` (tracking refs and
  `branch.aitask-data.*` stay). Control: bare `push --batch` → `NO_REMOTE`
  (precondition that the fixture really has no configured remote).
  Then `-c remote.origin.url=$FX_REMOTE -c remote.origin.fetch=+refs/heads/*:refs/remotes/origin/*
  push --batch` → `PUSHED`, exit 0, remote contains the local commit, and no
  "not pushed" warning on stderr. Discriminator: probes without the config →
  `NO_REMOTE` before any attempt (what the reviewer reproduced); push without
  it → `FAILED`; retry pull without it → non-ff persists → `FAILED`.
- **P3 other global options refused before anything runs.** `--no-pager push`
  and `-p push` → nonzero, message names the option, remote ref unchanged.
  `-C /tmp push` → existing redirect refusal.

Regression runs: `bash tests/test_ait_git_gateway_pull.sh`,
`bash tests/test_task_push.sh`, `bash tests/test_task_git.sh`;
`shellcheck .aitask-scripts/lib/task_utils.sh ait`.

### 4. Docs — `website/content/docs/commands/sync.md` `## ait git push`

Extend the global-options paragraph (current-state only): in front of `push`
only `-c` and `--config-env` are accepted; they apply to every push attempt and
the pull between attempts; any other global option is refused; arguments after
`push` other than `--batch` are ignored. Add an example line
`ait git -c core.sshCommand="ssh -i ~/.ssh/other" push`. Run
`python3 check_links.py --build` (in `website/`).

### 5. Step 9 — post-implementation (archival, push) per task-workflow.

## Verification

- The three test files above pass. Red proof: run the new P-cases against a
  fixture whose copied `ait` is the pre-change dispatcher (`git show HEAD:ait`
  into the fixture, not a worktree revert) — P1-prefixed and P2 must fail there
  (raw `git push` has no `--batch` and no retry).
- shellcheck clean; check_links clean.

## Risk

### Code-health risk: low
- Moving the `push` route from the dispatcher into `task_git_gateway` touches the path every workflow push takes (`./ait git push`); bare-form behaviour is unchanged and pinned by `test_task_push.sh` Tests 8/15 plus P1 · severity: low · → mitigation: none (covered by step 3 regressions)

- The push-cycle probes (`_task_push_has_remote` / `_unpushed_count` / `_upstream`) are shared with `task_sync` and `task_data_converge`; routing them through `_task_push_git` must leave those callers unchanged (empty array → identical argv) · severity: low · → mitigation: none (`test_task_push.sh` / sync suites rerun in step 3)

### Goal-achievement risk: low
- Option-prefixed push changes behaviour for two input shapes that used to reach raw git: non-config global options are now refused, and positional arguments after `push` (e.g. `origin other-branch`) are now ignored like the bare form · severity: low · → mitigation: none (documented in step 4; matches the bare form's existing contract)
