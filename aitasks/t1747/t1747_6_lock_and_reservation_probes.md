---
priority: high
effort: high
depends: [t1747_5]
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
anchor: 1733
created_at: 2026-09-09 11:14
updated_at: 2026-09-09 11:14
---

## Context

Child of t1747 (full audit: `aiplans/p1747_sweep_failopen_git_probes.md`; the
rule and canonical fix shape: `aidocs/framework/failopen_git_probes.md`, landed
by t1747_1).

Covers **audit rows A8, A8b and A12** — two files, one theme: probes that decide
whether to **take or release a lock**. Implement in two named phases.

---

# Phase 6a — `aitask_merge_task.sh`: a tri-state helper API and EVERY consumer

These are **not** three-call-site fixes. The helpers at `:81-83` have 7 and 8
consumers across four commands: pre-merge admission (`:168`, `:171`), post-merge
verdict rendering (`:213`), normal abort and reservation release (`:251`-`:266`),
force-release (`:406`-`:424`), and dry-run remedy guidance (`:466`-`:478`).
Fixing only force-release would leave the other paths reading an unreadable
repository as clean / no-merge.

## The defects

```bash
_merge_head_present() { [[ -f "$(git rev-parse --git-dir)/MERGE_HEAD" ]]; }
_unmerged_paths()     { git diff --name-only --diff-filter=U 2>/dev/null || true; }
_tree_dirty_tracked() { git status --porcelain -uno 2>/dev/null | grep -c . || true; }
```

- **A8 `_tree_dirty_tracked`** prints `0` both when the tree is clean and when
  `git status` failed: the pipeline hides git's rc, `grep -c` then prints `0`
  and exits 1, absorbed by `|| true`. It is the **post-`reset --hard`
  verification** at `:424`, so a failed probe reports `FORCE_RELEASED` over an
  unverified tree.
- **A8b `_merge_head_present`** — a failed `rev-parse` yields empty, so the test
  degrades to `[[ -f "/MERGE_HEAD" ]]` ⇒ "no merge in progress". It is the
  **remedy selector**.
- `_unmerged_paths` has the same `|| true` shape and gets the same treatment.
- `_head_branch` (`:84`) **stays as-is**: empty already reads as detached ⇒
  refuse, which is fail-closed.

## The sentinel-value trap — measured, do not skip this

The obvious fix (return a magic value) is wrong in **both** spellings, because
`_tree_dirty_tracked`'s value is consumed by `[[ "$(…)" -gt 0 ]]`, an
*arithmetic* context:

| sentinel | what `[[ "$s" -gt 0 ]]` actually does |
|---|---|
| `"unverified"` | bash resolves it as a **variable name**; under this script's `set -u` (`:25`) it **aborts the script** — mid-force-release, possibly after the lock dir was removed |
| `-1` or `""` | evaluates false ⇒ silently reads as **clean** — a brand-new fail-open |

So the unverified state travels on the **exit status**, never on stdout:

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

Both bodies were run in a scratch repo, with and without a `PATH` shim failing
`status --porcelain` / `rev-parse --git-dir`: `rc 0` with the right value when
the probe works, `rc 2` with empty stdout when it fails, and no `set -e` trip.

**Every `if _merge_head_present; then` must be rewritten.** A bare `if` treats
rc 2 as false — i.e. re-creates the exact fail-open. The refactor is complete
only when no call site consumes these helpers bare.

## Consumer dispositions

| consumer | today's fail-open consequence | disposition on unverified |
|---|---|---|
| `:168` `_merge_head_present` — pre-merge admission | admits a merge onto a tree with stale merge residue | `PREFLIGHT_UNVERIFIED:merge_state`, **release** (pre-merge refusals release, per the file's contract at `:188`) |
| `:171` `_tree_dirty_tracked` — pre-merge admission | admits a merge onto a dirty tree | `PREFLIGHT_UNVERIFIED:tree_state`, release |
| `:213` `_unmerged_paths` — verdict rendering | a real conflict reported as `MERGE_FAILED`, sending the caller down the wrong recovery | distinct verdict naming the unverified conflict state; reservation retained either way, so this one is honesty, not safety |
| `:251` `_merge_head_present` — abort branch selection | skips `merge --abort` on a real mid-merge tree, then releases via `RELEASED_NO_MERGE` | `ABORT_UNSAFE:merge_state_unverified`, **do not release** |
| `:254-255` post-abort verification | `ABORTED` + release over a tree that may still hold `MERGE_HEAD` | `ABORT_FAILED:state unverified` |
| `:260,:263,:266` residue checks | releases the reservation over unread residue | `ABORT_UNSAFE:<probe>_unverified`, do not release |
| `:406` force-release remedy selector | a mid-merge tree falls to the `elif` at `:414`: with `--abort-merge` it is refused as `WRONG_REMEDY:no_merge_head` (**blocking the correct remedy**); with `--reset-hard` it runs `git reset --hard HEAD` **over a merge in progress** — the more destructive remedy, chosen because the probe could not be read | `RECOVERY_FAILED:merge state unverified` **before any remedy runs** |
| `:411`, `:424` post-remedy verification | `FORCE_RELEASED` over an unverified tree | `RECOVERY_FAILED:<tree\|merge> state unverified` |
| `:466-478` dry-run guidance | prints a **wrong remedy flag**, and a copy-paste command line carrying it | print `residue: UNVERIFIED — cannot determine remedy`, and emit **no** remedy flag in the copy-paste line. Never hand the user a destructive flag chosen from an unread probe |

Verify these line numbers against the tree when the task runs; the audit was
taken at t1747 planning time.

## Making the coverage claim executable

Carry a **call-site table** for the three helpers in the plan, and ship a test
asserting the set of call sites in `aitask_merge_task.sh` equals that table — so
a ninth consumer cannot be added bare. Scope is deliberately one file and three
known function names, not a tree-wide search for intent.

---

# Phase 6b — `aitask_lock.sh:195`: the lock-existence probe (A12)

```bash
        if git ls-tree "$current_tree_hash" -- "$lock_file" 2>/dev/null | grep -q "$lock_file"; then
```

A failed `ls-tree` produces no output, `grep -q` is false, and **the entire
lock-exists block at `:195-276` is skipped** — and with it *every* liveness
gate: `LOCK_LIVE_HOLDER`, `LOCK_UNVERIFIABLE_HOLDER` and `LOCK_RECLAIM`. That is
a silent reprise of the t1466 defect those gates exist to prevent — two live
agent sessions owning one task.

**Fix:** capture the `ls-tree` rc; a non-zero rc is **unverified** ⇒ `die_code`
with a distinct message saying the lock state could not be read, never "no lock,
acquiring".

**Partial existing mitigation — state it, do not over-claim.** `parent_hash` and
`current_tree_hash` at `:189-190` are **un**suppressed under `set -euo pipefail`,
so an unreachable ref already kills the script before the probe. The residual is
a resolvable tree whose `ls-tree` nonetheless fails: narrower, but its
consequence is a total mutex bypass.

---

## Verification

Every row gets both directions, plus the probe-only **mutant control** required
of every t1747 child (follow `tests/test_fold_mark.sh::install_prefix_amend_probe`:
regress only the probe, fail loudly on a stale anchor, verify the substitution
landed, assert the rest survived), driven by argv-keyed `PATH` `git` shims that
fail exactly one verb.

| command under test | shim fails | fail-closed assertion | permit assertion |
|---|---|---|---|
| `begin` (`:168`, `:171`) | `rev-parse --git-dir` / `status -uno` | `PREFLIGHT_UNVERIFIED:*`, reservation **released** (not stranded) | a clean tree on an existing branch still reaches `MERGE_OK` |
| `begin` verdict (`:213`) | `diff --diff-filter=U` | verdict names the unverified conflict state; reservation **retained** | a real conflict still reports `MERGE_CONFLICT:<files>` |
| `abort` (`:251`-`:266`) | each helper, one at a time | `ABORT_UNSAFE:*_unverified` / `ABORT_FAILED`, lock dir **still present** | a real `MERGE_HEAD` still aborts and releases (`ABORTED`); a clean tree still reports `RELEASED_NO_MERGE` |
| `force-release` (`:406`, `:411`, `:424`) | `rev-parse --git-dir` / `status -uno`, **each branch separately** — `:406` and `:411` fail differently | `RECOVERY_FAILED:*`, lock dir **still present**, and **no `reset --hard` ran** | a real `MERGE_HEAD` still selects `--abort-merge`; a real dirty-no-merge tree still selects `--reset-hard` and reports `FORCE_RELEASED` |
| `force-release --dry-run` (`:466`-`:478`) | `rev-parse --git-dir` | prints `UNVERIFIED`, copy-paste line carries **no** remedy flag | a real `MERGE_HEAD` still prints ` --abort-merge` in the copy-paste line |
| A12 `aitask_lock.sh:195` | `ls-tree` | acquisition **refused**; the other session's lock file **unchanged** on the locks branch | an absent lock still acquires; an existing live lock still emits `LOCK_LIVE_HOLDER` |

Assert each fixture's **precondition** — identity *and* symptom — before
invoking the code, in the test and its control alike: "the probe returned empty"
is a symptom several unrelated fixture accidents produce.

The A12 permit row is load-bearing: `test_task_lock.sh`,
`test_lock_live_holder_gate.sh`, `test_lock_reclaim.sh` and `test_stale_lock.sh`
must stay green, or the fix has traded a fail-open mutex for one that refuses
legitimate claims.

```bash
bash tests/test_merge_lock_broker.sh
bash tests/test_merge_broker_rendered_verdicts.sh
bash tests/test_merge_lock_concurrency.sh
bash tests/test_task_lock.sh
bash tests/test_lock_live_holder_gate.sh
bash tests/test_lock_reclaim.sh
bash tests/test_stale_lock.sh
bash tests/test_lock_force.sh
shellcheck .aitask-scripts/aitask_merge_task.sh .aitask-scripts/aitask_lock.sh
```

Shellcheck baseline: `aitask_merge_task.sh` is clean apart from SC1091;
`aitask_lock.sh` has one pre-existing SC2086 at `:701`. New code must add none.

## Note on splitting

6a and 6b share no file and no test suite. If 6a's diff proves unwieldy,
splitting 6b into its own sibling is a clean cut — this grouping was a
deliberate choice at t1747 planning time, not a constraint.
