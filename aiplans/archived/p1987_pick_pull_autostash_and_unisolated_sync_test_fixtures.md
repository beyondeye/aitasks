---
Task: t1987_pick_pull_autostash_and_unisolated_sync_test_fixtures.md
Base branch: main
Output branch: main
---

# t1987 — pick-pull autostash, converge ignored-overwrite, unisolated sync fixtures, cd-guard lint

## Context

t1792 made `ait sync` immune to a user's `rebase.autoStash` / `merge.autoStash`
and made its fast-forward refuse to overwrite ignored files. Its review found
four leftovers outside its scope:

1. `_task_pull_rebase` (`.aitask-scripts/lib/task_utils.sh:1316`) runs
   `pull --rebase` with no `--no-autostash`. A user's `rebase.autoStash=true`
   would make it stash other sessions' dirty files in the shared
   `.aitask-data` worktree and apply them again.
2. `task_data_converge`'s fast-forward (`task_utils.sh:1646`) runs
   `merge --ff-only` with neither `--no-autostash` nor `--no-overwrite-ignore`.
   Git's default overwrites an ignored file such as `userconfig.yaml` when an
   incoming commit writes it.
3. `tests/test_sync.sh`, `tests/test_sync_branch_mode_automerge.sh` and
   `tests/test_task_push.sh` inherit the developer's global and system git config.
   This machine's global config sets `pull.rebase=true`, `rerere.enabled=true`,
   `rerere.autoupdate=true` and `user.*`.
4. `tests/test_linked_trail_jump_live.sh` has a `cd` at line 164 but never calls
   `enter_scratch_cwd`, so `tests/test_cd_guard_lint.sh` fails on the live tree
   (re-confirmed: 91 passed, 1 failed).

**Coordination with t1956 (decided at planning time).** t1956 is `Ready`, not
started, and has effort high. t1912, t1678 and t1984 are also all `Ready`. No
`Implementing` task touches these files. t1956 does not fully cover the two
task_utils items:
- `_task_pull_rebase` has two callers: `task_sync` (L817) and `task_push`'s
  retry (L980). t1956 rewires only `task_sync()`, so the push-retry pull falls
  outside its scope.
- `task_data_converge` is in t1956's scope only "if it still has callers when
  this task is planned", and t1912 plans to remove it. Its caller
  (`verified_update_lib.sh:127`) still exists today.

Both fixes are therefore made here. They are flag additions that match t1956's
own goal 3 ("no stash or autostash"; keep `--no-autostash --no-overwrite-ignore`).
After the commit, a note goes to t1956 so that its extraction keeps them.

## Implementation

### Pre-phase (risk mitigations)

1. [baseline_isolated_fixture_run] Before any edit, run each of
   `tests/test_sync.sh`, `tests/test_sync_branch_mode_automerge.sh` and
   `tests/test_task_push.sh` twice, saving the full output under the
   scratchpad:
   - (a) as-is;
   - (b) with `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1` exported by
     the invoker. That is exactly the environment the file-scope isolation in
     step 5 creates.

   Record the final `Results:` / PASS / FAIL / TOTAL line of each run. Also
   record which failures, if any, run (a) already has: that is the baseline,
   and a pre-existing failure is not this task's regression. Any cell that
   passes in (a) and fails in (b) names a fixture that depends on global config.
   Fix that fixture with explicit per-repo config (step 5's rule) before
   step 5 lands, then re-run (b) until it matches (a).

### 1. `_task_pull_rebase`: never autostash (`task_utils.sh` ~L1316)

```bash
out="$(_ait_data_git "${AIT_RECONCILE_GIT_OPTS[@]}" pull --rebase --no-autostash --quiet 2>&1)" || rc=$?
```
Add a two-line comment above it, in the style of the `aitask_sync.sh` L2062
comment: `--no-autostash` (t1792, t1987) stops a user's `rebase.autoStash` from
stashing and re-applying other live sessions' uncommitted edits in the shared
worktree, so the pull refuses on a dirty worktree just as it does under git's
default. The flag sits in the function, so both callers (`task_sync`,
`task_push`'s retry) get it.

### 2. `task_data_converge`: no autostash, no ignored overwrite (~L1646)

```bash
if ff_err="$(_ait_data_git merge --ff-only --no-autostash --no-overwrite-ignore --quiet "$upstream" 2>&1)"; then
```
Classify the refusal. Keep the existing `dirty_worktree → ff_blocked` remap
first, and add one converge-local arm, used only when that remap did not fire:
```bash
reason="$(_task_push_classify "" "$ff_err")"
if [[ "$reason" == "dirty_worktree" ]]; then
    reason="ff_blocked"
elif [[ "$ff_err" == *"untracked working tree files would be overwritten"* ]]; then
    reason="ff_ignored"
fi
```
Before relying on that substring, probe git's exact refusal text in a scratchpad
repo (an ignored local file plus an incoming force-added copy). Adjust the match
to what git prints.

Update the header comment (~L1575–1580): name the two flags and say why.
`merge.autoStash` would rewrite other sessions' dirty files, and an incoming
commit could overwrite an ignored local file such as `userconfig.yaml`.

### 3. Hint for the new reason code (`_task_push_reason_hint`, ~L1517)

Add a converge-only arm next to `ff_blocked` / `local_diverged`:
```
ff_ignored)
    echo "an incoming commit would overwrite a local untracked or ignored file (e.g. userconfig.yaml); nothing was changed — move the local file aside, then reconcile with './ait sync'" ;;
```
Consumer audit (done): the only other consumer of `TASK_CONVERGE_REASON` is
`verified_update_lib.sh:241`, which prints it free-form. No other code
enumerates the reason codes, and no doc names `ff_blocked`.

### 4. One shared isolation helper (`tests/lib/git_config_isolation.sh`, new)

Move `sync_isolate_git_config` out of `tests/lib/sync_fixture.sh` into a new,
side-effect-free lib, keeping its comment. sync_fixture.sh creates a mktemp
base, sets an EXIT trap and exports a tmux socket, so it cannot be sourced just
for the helper. The name stays the same, so the six existing call sites
(`run_sync`, plus the direct wrappers in `test_sync_failopen_probes.sh` and
`test_sync_deferral_and_quarantine.sh`) need no edit. `sync_fixture.sh`
sources the new lib through `$PROJECT_DIR`, which it already requires.

In the same lib, add `assert_git_config_isolated`. It proves that **this
shell's** isolation holds against a global config and a system config that the
check plants itself, so the result does not depend on the developer's machine.
Each probe is paired with a control showing the planted file **is** read once
that one isolation variable is removed for that one command. Only the probe
commands carry the overrides (`HOME`, `XDG_CONFIG_HOME`,
`GIT_CONFIG_SYSTEM`), so no fixture behaviour changes. The function requires
`asserts.sh`.
```bash
assert_git_config_isolated() {
    local d
    d="$(mktemp -d "${TMPDIR:-/tmp}/ait_gitiso_XXXXXX")" \
        || { assert_eq "git isolation probe: mktemp" "ok" "failed"; return 0; }
    mkdir -p "$d/home"
    printf '[aitTripwire]\n\tglobal = visible\n' > "$d/home/.gitconfig"
    printf '[aitTripwire]\n\tsystem = visible\n' > "$d/sysconfig"
    assert_eq "git isolation control: a planted global config is read without isolation" "visible" \
        "$(env -u GIT_CONFIG_GLOBAL HOME="$d/home" XDG_CONFIG_HOME="$d/xdg" git config --get aitTripwire.global 2>/dev/null)"
    assert_eq "git isolation: a planted global config never reaches this file" "" \
        "$(HOME="$d/home" XDG_CONFIG_HOME="$d/xdg" git config --get aitTripwire.global 2>/dev/null)"
    assert_eq "git isolation control: a planted system config is read without isolation" "visible" \
        "$(env -u GIT_CONFIG_NOSYSTEM GIT_CONFIG_SYSTEM="$d/sysconfig" git config --get aitTripwire.system 2>/dev/null)"
    assert_eq "git isolation: a planted system config never reaches this file" "" \
        "$(GIT_CONFIG_SYSTEM="$d/sysconfig" git config --get aitTripwire.system 2>/dev/null)"
    rm -rf "$d"
}
```
The cwd is the scratch dir, outside any repository, so `git config --get` reads
only the system, global and env scopes. `GIT_CONFIG_SYSTEM` needs git ≥ 2.32;
this machine has 2.55. Confirm while implementing that `assert_eq`'s return
status does not trip `test_sync.sh`'s `set -e` on a failing probe; the file
already calls `assert_eq` under `set -e`.

### 5. Isolate the three test files at file scope

**Placement rule:** after `asserts.sh` is sourced **and** after
`PASS=0 / FAIL=0 / TOTAL=0`, but before the first fixture or git command. The
initialisation would erase an earlier assertion's result, and the footer's
`FAIL` guard would then pass a failed check:
- `tests/test_sync.sh`: after the `asserts.sh` source (L21). The counters are
  already set at L13–15.
- `tests/test_sync_branch_mode_automerge.sh`: after the `asserts.sh` source
  (L56). The counters are already set at L52–54.
- `tests/test_task_push.sh`: after `CLEANUP_DIRS=()` (L18). `asserts.sh` is
  sourced at L10, but the counters are only set at L15–17. No fixture runs
  before L18: `test_scaffold.sh` only defines functions.

```bash
# Developer git config never reaches this file (t1987, same leak t1792 closed in
# sync_fixture.sh): per-repo user.* set by the fixtures still applies.
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
assert_git_config_isolated
```
**Why file scope rather than per call site:** the files run `aitask_sync.sh` from
53 inline sites (21, 30 and 2), and missing one would leak silently. In
`test_task_push.sh`, the code under test mostly runs in-process (`task_sync`,
`task_push`, `task_data_converge`), and that hits the same leak class. Tests 11
and 18 hand-pin `rebase.autoStash false` against it today; leave those pins as
they are. The per-repo `user.*` the fixtures set is repository config and still
applies.

If the pre-phase run (below) shows that a fixture depended on global config
(identity, `pull.rebase`, `push.autoSetupRemote`), fix that fixture with
explicit per-repo config. Never weaken the isolation to fix it.

### 6. cd-guard lint: `tests/test_linked_trail_jump_live.sh`

Right after `PROJECT_DIR=…` (line 33), use the repo's standard form:
```bash
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
```
Override audit (per the cwd-move rule): the file reads only `${TMPDIR:-/tmp}`
for `mktemp`. That is a system variable, absolute in practice, and every other
`enter_scratch_cwd` adopter reads it the same way (e.g. `test_task_push.sh`).
The other paths are absolute (`$FIXTURE_DIR`, `$PROJECT_DIR`, `$DRIVER`), and
`require_ait_python` resolves under `$HOME`. No anchoring is needed.

### 7. Regression cells (`tests/test_task_push.sh`)

Each copies an existing test's fixture. They pin the behaviour with
**per-repo** config, which file-scope isolation does not touch:

- **Test 11b**, the `task_push` retry ignores `rebase.autoStash`: Test 11's
  fixture with `git -C .aitask-data config rebase.autoStash true`. Expect
  `failed` / `dirty_worktree`. `init.txt` must keep its bytes and its
  inode+ctime. `git stash list` must be empty, and the remote is unchanged.
- **Test 18b**, the pick-time `task_sync` ignores `rebase.autoStash`: Test 18's
  fixture with `rebase.autoStash true`. Expect `failed` / `dirty_worktree`.
  `init.txt` bytes and identity are unchanged, `remote_only.txt` did not land,
  and the stash list is empty.
- **Test 28b**, converge ignores `merge.autoStash`: Test 28's fixture with
  `git config merge.autoStash true`. Expect `fast-forwarded`. `mine.txt` bytes
  **and** inode+ctime are unchanged, and the stash list is empty.
- **Test 29b**, converge never overwrites an ignored file: add `userconfig.yaml`
  to `.git/info/exclude` and create a local copy containing "mine". The other
  clone force-adds `userconfig.yaml` ("theirs") and pushes. Expect `blocked` /
  `ff_ignored`. The local bytes stay "mine", porcelain shows `!!`, HEAD is
  unchanged, and the warning contains "move the local file aside".

`file_ident` comes from `test_sync_autostash_ignored.sh`: inode plus
`st_ctime_ns` via python3, because a stash round trip restores the bytes but
rewrites the file. Add it as a local helper in `test_task_push.sh`.

### Post-implementation

- Commit the code: `bug: Never autostash or overwrite ignored files in the pick
  pull and converge; isolate sync test fixtures (t1987)`. Name the paths
  explicitly. The worktree also holds another session's
  `brainstorm_app.py` / `test_brainstorm_from_sections_reload.py`, which must not
  be staged.
- Run `./ait note 1956 --from 1987` to say that `_task_pull_rebase` now passes
  `--no-autostash` and that `task_data_converge`'s fast-forward passes
  `--no-autostash --no-overwrite-ignore` (new reason `ff_ignored`). Its
  extraction must keep them, and Tests 11b/18b/28b/29b pin them. Hedge: "as of
  <commit>".
- Step 9 (Post-Implementation): review, archive and push per the shared
  workflow.

## Verification

- `bash tests/test_task_push.sh`, `bash tests/test_sync.sh`,
  `bash tests/test_sync_branch_mode_automerge.sh`: all pass, and TOTAL equals
  the pre-phase baseline plus the new assertions.
- `bash tests/test_cd_guard_lint.sh`: 92/92 (the live-tree cell turns green).
- `bash tests/test_linked_trail_jump_live.sh`: still passes after the cwd move.
- Helper move regression: `test_sync_autostash_ignored.sh` (C7 pins
  `run_sync`'s isolation), `test_sync_failopen_probes.sh`,
  `test_sync_deferral_and_quarantine.sh`, `test_sync_guarded_merge.sh`,
  `test_metadata_partial_sync_recovery.sh` (converge's Cell A fast-forward).
- **Mutants**, each in an isolated scratchpad copy of `ait`, `.aitask-scripts`
  and `tests`. Never restore files in the shared worktree. Each must turn only
  its own cells red:

  | mutant | change | red |
  |---|---|---|
  | M1 | drop `--no-autostash` from `_task_pull_rebase` | 11b, 18b |
  | M2 | drop `--no-autostash` from converge's ff | 28b |
  | M3 | drop `--no-overwrite-ignore` from converge's ff | 29b |
  | M4 | drop the `ff_ignored` arm | 29b (reason + hint only) |
  | M5 | drop the file-scope `sync_isolate_git_config` call from one file (once per file) | that file's two "never reaches this file" probes; both controls stay green; the file **exits non-zero** |
  | M6 | the helper exports only `GIT_CONFIG_GLOBAL` (no `GIT_CONFIG_NOSYSTEM`) | the system probe in each of the three files and C7 stays green |

  M5 and M6 go red on any machine: the probes plant their own configs, so they
  never depend on the developer having a global or system config. In each run
  check the file's **exit status**, not only its `FAIL:` lines.

  M5's non-zero exit is also what pins the placement rule. With the block above
  `test_task_push.sh`'s counter init, the same failing probe would print `FAIL:`
  but the file would still exit 0. In the M5 run of `test_task_push.sh`, also
  confirm that the summary's FAIL count includes the probe failures.
- `shellcheck .aitask-scripts/lib/task_utils.sh` (no new findings) and
  `bash -n` on every edited test file.

## Risk

### Code-health risk: low
- File-scope isolation changes the environment of the three files' own fixture git commands. The developer's global `pull.rebase`, `push.autoSetupRemote` and `user.*` stop reaching them, so a fixture with a hidden dependency could break at setup · severity: low · → mitigation: inline pre-phase baseline_isolated_fixture_run
- `--no-autostash` changes the pick pull and push retry for users with `rebase.autoStash=true`. They now refuse on a dirty worktree, as under git's default, instead of stashing other sessions' edits. This is the intended fix · severity: low · → mitigation: none (pinned by Tests 11b/18b)
- Moving `sync_isolate_git_config` into a new lib touches every test that sources `sync_fixture.sh` · severity: low · → mitigation: none (the helper-move regression run, including C7)
- An isolation assertion placed before a file's `PASS/FAIL/TOTAL=0` init would have its failure erased, and the file would exit 0 · severity: low · → mitigation: none (step 5's placement rule, pinned by M5's exit-status check)

### Goal-achievement risk: low
- The `ff_ignored` classification depends on git's exact refusal text for an ignored-file overwrite · severity: low · → mitigation: none (step 2's probe plus Test 29b and mutant M4)

### Planned mitigations
- timing: pre-phase | name: baseline_isolated_fixture_run | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: file-scope isolation breaking a fixture that silently depends on global git config | desc: run the three test files as-is and under invoker-exported GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 before editing, and fix any fixture whose result differs

## Final Implementation Notes
- **Actual work done:**
  - **Code** (`.aitask-scripts/lib/task_utils.sh`):
    - `_task_pull_rebase` runs `pull --rebase --no-autostash`. Both callers get it: `task_sync`, the pick-time pull, and `task_push`'s retry.
    - `task_data_converge`'s fast-forward runs `merge --ff-only --no-autostash --no-overwrite-ignore`.
    - A refusal containing git's "untracked working tree files would be overwritten" is now the new reason `ff_ignored`. It is checked only after the existing `dirty_worktree → ff_blocked` remap.
    - The new hint arm in `_task_push_reason_hint` says to move the local file aside, then run `./ait sync`.
  - **Tests:**
    - New `tests/lib/git_config_isolation.sh` (side-effect free). It holds `sync_isolate_git_config`, moved from `sync_fixture.sh`, which now sources the lib, so the 6 existing callers are unchanged. It also holds `assert_git_config_isolated`: planted global (temp `HOME`) and system (`GIT_CONFIG_SYSTEM`) configs, each probe paired with a control that removes one isolation variable for one command.
    - `test_sync.sh`, `test_sync_branch_mode_automerge.sh` and `test_task_push.sh` are isolated at file scope. The block sits after the counter init in every file. In `test_task_push.sh` that is after `CLEANUP_DIRS=()`, not next to the `asserts.sh` source.
    - `test_task_push.sh` gains Tests 11b, 18b, 28b and 29b (27 assertions) and the `file_sha` / `file_ident` helpers.
    - `test_linked_trail_jump_live.sh` calls `enter_scratch_cwd`, which fixes the cd-guard lint failure.
  - **Pre-phase `baseline_isolated_fixture_run`:** run on a `git archive HEAD` copy. As-is and under invoker-exported isolation the results were identical: test_sync 42/42, automerge 166/166, task_push 365/365. No fixture depended on global config, so no fixture needed per-repo fixes.
  - **Results after the change:**
    - task_push 396/396, test_sync 46/46, automerge 170/170 (4/4 passes run concurrently after the flake fix);
    - cd_guard_lint 92/92, linked_trail_jump_live 25/25;
    - sync_autostash_ignored 83/83 (C7 green);
    - sync_guarded_merge 147, sync_deferral_and_quarantine 138, sync_failopen_probes 51 and metadata_partial_sync_recovery 38, all passing.
  - **Mutants** (isolated scratchpad copies):
    - M1 fails 11b+18b only. With autostash on, the pulls succeed and the in-flight file is rewritten (inode+ctime change).
    - M2 fails 28b's identity check only.
    - M3 fails only 29b; the ignored file really is overwritten ("mine" → "theirs").
    - M4 fails 29b's reason and hint only (`unknown`).
    - M5, run on each file, fails both "never reaches" probes and the file exits 1. In `test_task_push.sh` the FAIL count includes the probes, which pins the placement after the counter init.
    - M6 fails the system probe in all three files, and C7 stays green.
  - `shellcheck` finding count for `task_utils.sh` is unchanged.
- **Deviations from plan:**
  - **Pre-approval review.** The user flagged two problems. (1) The isolation assertion was first placed right after the `asserts.sh` source, but `test_task_push.sh` sets its counters later, which would have erased a failure. (2) The first tripwire read ambient config and was machine-dependent. Both were fixed before approval: the placement rule, and planted-config probes with controls.
  - **Baseline contamination.** The first baseline ran against the live tree while `task_utils.sh` was being edited; those tests source it live. It was stopped and re-run from a `git archive HEAD` copy.
  - **Added with user approval:** the `_local_log_has` fix in `test_sync_branch_mode_automerge.sh`.
- **Issues encountered:** `test_sync_branch_mode_automerge.sh` failed one "commit is still reachable/intact" cell intermittently under parallel load. It failed in 3 of 4 runs after the change, a different cell each time, and passed when run alone. The cause predates this task:
  - `_local_log_has` ran `git log --format=%s | grep -qxF` under the file's `set -o pipefail`.
  - `git log` flushes per commit into a pipe. `grep -q` exits on the first match, git's next write raises SIGPIPE, and pipefail turns a present commit into "absent".
  - Reproduced with both processes pinned to one CPU: 27/400 false negatives with pipefail, 0/400 without it.
  - With the user's approval it was fixed here by dropping `-q` and redirecting to `/dev/null`. The pinned probe then gave 0/400, with no false positives on an absent subject.
  - `_local_log_lacks` (`! _local_log_has`) had the mirror-image false pass.
  - The code change could not cause it: `aitask_sync.sh` calls none of the edited functions, and it also failed in M5, where isolation is removed.
- **Key decisions:**
  - **Fixed here, not left to t1956.** t1956 rewires only `task_sync()`, so the push-retry caller of `_task_pull_rebase` is outside its scope. `task_data_converge` is in its scope only conditionally, pending t1912. Both fixes match t1956's goal 3.
  - **Isolation at file scope, not per call site.** There are 53 inline `aitask_sync.sh` sites, and `test_task_push.sh` runs the code under test in-process.
  - **The new reason is converge-local.** The `ff_ignored` arm lives in `task_data_converge`, not in the shared `_task_push_classify`, so push and pull classification is unchanged.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/task_utils.sh:1319` — a behind-only `pull --rebase` in `_task_pull_rebase` still overwrites an ignored local file that an incoming commit writes (`pull --rebase` has no `--no-overwrite-ignore`). This is t1956's scope: its goal 2 routes behind-only through the fast-forward. Handed over by note, not a new task.
  - `.aitask-scripts/aitask_crew_addwork.sh:328` and `.aitask-scripts/aitask_crew_setmode.sh:125` — raw `git pull --rebase` without `--no-autostash`, the same class as this task's fix. Found by code reading; whether crew worktrees ever hold another live session's uncommitted edits was not verified.
