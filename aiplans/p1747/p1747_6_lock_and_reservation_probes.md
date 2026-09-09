---
Task: t1747_6_lock_and_reservation_probes.md
Parent Task: aitasks/t1747_sweep_failopen_git_probes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1747_6 — Lock and reservation probes: a tri-state API and every consumer

## Context

Audit rows A8, A8b, A12 (see `aidocs/framework/failopen_git_probes.md`). Two
files, one theme: probes that decide whether to **take or release a lock**.
Implemented in two named phases. Verify every line number against the tree
before editing — the audit was taken at t1747 planning time.

---

## Phase 6a — `aitask_merge_task.sh`

### Why this is not a three-call-site fix

The helpers at `:81-83` have **7 and 8 consumers** across four commands:
pre-merge admission (`:168`, `:171`), post-merge verdict rendering (`:213`),
normal abort and reservation release (`:251`-`:266`), force-release
(`:406`-`:424`), and dry-run remedy guidance (`:466`-`:478`). Hardening the
helpers while any caller still reads them bare leaves the site *looking* fixed
and behaving unchanged.

### The sentinel-value trap — measured; do not skip

`_tree_dirty_tracked`'s value is consumed by `[[ "$(…)" -gt 0 ]]`, an
**arithmetic** context. A magic stdout value is wrong in both spellings:

| sentinel | what `[[ "$s" -gt 0 ]]` actually does |
|---|---|
| `"unverified"` | bash resolves it as a **variable name**; under this script's `set -u` (`:25`) it **aborts the script** — mid-force-release, possibly after the lock dir was removed |
| `-1` or `""` | evaluates false ⇒ silently reads as **clean** — a brand-new fail-open |

So the unverified state travels on the **exit status**, never on stdout.

### The API

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

`_unmerged_paths` (`:82`) gets the same treatment. `_head_branch` (`:84`)
**stays as-is** — empty already reads as detached ⇒ refuse, which is fail-closed.

**Every `if _merge_head_present; then` must be rewritten.** A bare `if` treats
rc 2 as false — i.e. re-creates the exact fail-open. The refactor is complete
only when no call site consumes these helpers bare.

Never let an empty git-dir compose into a filesystem path:
`[[ -f "/MERGE_HEAD" ]]` is the bug in miniature.

### Consumer dispositions

| consumer | today's fail-open consequence | disposition on unverified |
|---|---|---|
| `:168` `_merge_head_present` — pre-merge admission | admits a merge onto a tree with stale merge residue | `PREFLIGHT_UNVERIFIED:merge_state`, **release** (pre-merge refusals release, per the contract at `:188`) |
| `:171` `_tree_dirty_tracked` — pre-merge admission | admits a merge onto a dirty tree | `PREFLIGHT_UNVERIFIED:tree_state`, release |
| `:213` `_unmerged_paths` — verdict rendering | a real conflict reported as `MERGE_FAILED`, sending the caller down the wrong recovery | a distinct verdict naming the unverified conflict state; reservation retained either way, so this one is honesty, not safety |
| `:251` `_merge_head_present` — abort branch selection | skips `merge --abort` on a real mid-merge tree, then releases via `RELEASED_NO_MERGE` | `ABORT_UNSAFE:merge_state_unverified`, **do not release** |
| `:254-255` post-abort verification | `ABORTED` + release over a tree that may still hold `MERGE_HEAD` | `ABORT_FAILED:state unverified` |
| `:260,:263,:266` residue checks | releases the reservation over unread residue | `ABORT_UNSAFE:<probe>_unverified`, do not release |
| `:406` force-release remedy selector | a mid-merge tree falls to the `elif` at `:414`: with `--abort-merge` it is refused as `WRONG_REMEDY:no_merge_head` (**blocking the correct remedy**); with `--reset-hard` it runs `git reset --hard HEAD` **over a merge in progress** — the more destructive remedy, chosen because the probe could not be read | `RECOVERY_FAILED:merge state unverified`, **before any remedy runs** |
| `:411`, `:424` post-remedy verification | `FORCE_RELEASED` over an unverified tree | `RECOVERY_FAILED:<tree\|merge> state unverified` |
| `:466-478` dry-run guidance | prints a **wrong remedy flag**, and a copy-paste command line carrying it | print `residue: UNVERIFIED — cannot determine remedy`, and emit **no** remedy flag in the copy-paste line. Never hand the user a destructive flag chosen from an unread probe |

Adding new verdict strings is a **wire-contract change**: check every consumer
of these verdicts (`aitask_merge_task.sh`'s callers, the broker tests, and the
skills that parse them) before choosing the spellings.

### Making the coverage claim executable

Carry the call-site table in this plan, and ship a test asserting the set of
call sites in `aitask_merge_task.sh` equals it — so a ninth consumer cannot be
added bare. Scope is deliberately one file and three known function names, not a
tree-wide search for intent.

---

## Phase 6b — `aitask_lock.sh:195` (A12)

```bash
        if git ls-tree "$current_tree_hash" -- "$lock_file" 2>/dev/null | grep -q "$lock_file"; then
```

A failed `ls-tree` produces no output, `grep -q` is false, and **the entire
lock-exists block at `:195-276` is skipped** — and with it *every* liveness
gate: `LOCK_LIVE_HOLDER`, `LOCK_UNVERIFIABLE_HOLDER`, `LOCK_RECLAIM`. That is a
silent reprise of the t1466 defect those gates exist to prevent: two live agent
sessions owning one task.

**Fix:** capture the `ls-tree` rc (hoist it out of the pipeline so git's status
is visible at all); a non-zero rc is **unverified** ⇒ `die_code` with a distinct
message saying the lock state could not be read — never "no lock, acquiring".

**Partial existing mitigation — state it, do not over-claim.** `parent_hash` and
`current_tree_hash` at `:189-190` are **un**suppressed under `set -euo pipefail`,
so an unreachable ref already kills the script before the probe. The residual is
a resolvable tree whose `ls-tree` nonetheless fails: narrower, but its
consequence is a total mutex bypass.

Pick a `die_code` value that does not collide with the existing 11 / 13 / 14
codes, and check whether `aitask_pick_own.sh` / task-workflow Step 4 needs to
learn it — an unknown exit code there would surface as a bare failure.

---

## Verification

Every row gets both directions plus the probe-only **mutant control** required
of every t1747 child (follow `tests/test_fold_mark.sh::install_prefix_amend_probe`:
regress only the probe, hard-fail on a stale anchor, verify the substitution
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
is a symptom several unrelated fixture accidents produce. For the force-release
rows the fixture must be one where the remedy **would otherwise have run**, so
the refusal can only be the unread probe.

The A12 permit row is load-bearing: `test_task_lock.sh`,
`test_lock_live_holder_gate.sh`, `test_lock_reclaim.sh` and `test_stale_lock.sh`
must stay green, or the fix has traded a fail-open mutex for one that refuses
legitimate claims — which on the lock path means nobody can pick a task.

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

Baseline: `aitask_merge_task.sh` clean apart from SC1091; `aitask_lock.sh` has
one pre-existing SC2086 at `:701`. New code must add none.

## Note on splitting

6a and 6b share no file and no test suite. If 6a's diff proves unwieldy,
splitting 6b into its own sibling is a clean cut — this grouping was a
deliberate choice at t1747 planning time, not a constraint.

## Risk

### Code-health risk: medium
- 6a changes three shared helpers and ~20 call sites across four commands, and
  adds new verdict strings to a wire contract. · severity: medium · →
  mitigation: none needed as a task — the call-site table plus its equality test
  is the containment, and it is the specific control that makes "every consumer"
  checkable rather than promised.

### Goal-achievement risk: medium
- The lock path is how every task is picked. An over-eager refusal in 6b would
  block all work, and one in 6a would strand merge reservations. · severity:
  medium · → mitigation: none needed as a task — every row above carries a
  permit assertion alongside its fail-closed one, and 6b refuses only on a real
  non-zero `ls-tree`, never on an empty result.
- Refusing to release a reservation (6a's abort dispositions) can strand a lock.
  · severity: medium · → mitigation: none needed as a task — `force-release` is
  the designed recovery for exactly that, and every new refusal message must
  name it. If any refusal has no recovery route, say so rather than shipping a
  dead end.
