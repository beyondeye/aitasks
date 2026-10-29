---
Task: t2164_release_registry_lock_before_die_in_projects_verbs.md
Base branch: main
Output branch: main
---

# t2164 — registry lock after a `die` inside a locked section of `ait projects`

## Context

t2163's Step 8b review flagged that six `die` calls in `.aitask-scripts/aitask_projects.sh`
run after `registry_lock_or_die` and never call `registry_lock_release`:

- `cmd_update`: "No registered projects." and "Project '<name>' is not registered."
- `set_registry_group`: "Project '<name>' is not registered." (group set/unset)
- `rename_registry_group`: "No registered project has group '<old>'."
- `cmd_add`: the invalid `project.project_group` config-slug die
- `group sync`: the invalid config-slug die

The task asked us to (a) find out whether the lock is really left behind, checking
`cmd_doctor`'s `( cmd_update … )` subshell first, and (b) release the lock before
each die, then pin that with a test.

### Measured on c0483ba6e (this session, in scratch registries)

- **No lock is left behind on any of these paths today.** `registry_lock_acquire`
  (`.aitask-scripts/lib/registry_lock.sh`) installs
  `trap "registry_lock_release '$dir'" EXIT` on every successful acquire, and
  `die` (`lib/terminal_compat.sh`) calls `exit 1`. So the EXIT trap releases the
  lock by owner token. I ran all six die paths as standalone commands, checked
  that each printed its intended error, and found `projects.yaml.lockd` absent
  after every one.
- **The doctor case:** the lock records the **parent (doctor) pid** (`$$`), not
  the subshell's `BASHPID` (seen: subshell BASHPID 3393613, recorded 3393601).
  So a lock leaked there **would** have a live holder: stale-pid reclaim would
  not free it, and the doctor's next locked verb would wait out the 10 s acquire
  and die. It does not leak, though. The subshell sets its own EXIT trap when it
  acquires, so its `die` releases the lock. After `( cmd_update ghost … )` died,
  `lockd` was absent and the next `cmd_update` acquired the lock in 0 s.
- No other `trap … EXIT` exists in `aitask_projects.sh` or the libraries it
  sources (`atomic_write.sh` documents that it deliberately sets none), so
  nothing overwrites the adapter's trap.

**Consequence:** adding explicit releases (or a `die_locked` helper) would be dead
code, because the EXIT trap already releases the lock. The real gap is that
**nothing pins this behaviour.** If someone drops the trap or adds a
`trap … EXIT` to this script, these exits would start leaking the lock with no
failing test. The doctor case would then become a 10 s stall followed by a hard
`die` inside a live session. So this task ships a regression test and a comment
recording why no explicit release is needed. It does not change the release
mechanics.

## Implementation

### 1. Comment at the lock helper — `.aitask-scripts/aitask_projects.sh`

Extend the comment above `registry_lock_or_die()` (around lines 51-55) with:

```bash
# Every exit after a successful acquire — a `die` inside the locked section
# included, and a `( cmd_update … )` subshell in cmd_doctor too — releases the
# mutex through the EXIT trap registry_lock_acquire installs (lib/registry_lock.sh),
# so a die under the lock needs no explicit release. Do not install another
# `trap … EXIT` in this script: bash keeps one, and replacing it would leak the
# lock on every such die (pinned by tests/test_projects_lock_released_on_die.sh,
# t2164).
```

`load_registry_or_die --locked` keeps its explicit release. It is harmless, and
removing it is outside this task's scope.

### 2. New test — `tests/test_projects_lock_released_on_die.sh`

Use the same scaffold as `tests/test_projects_unreadable_registry.sh`: `set -e`,
PASS/FAIL/TOTAL, `tests/lib/asserts.sh`, a `mktemp -d` root with an EXIT cleanup
trap, `AITASKS_PROJECTS_INDEX` pointing at the scratch registry, and
`make_project` fixtures. No assertion runs inside a `( … )` subshell, so the
file-backed counters are not needed.

Fixtures:
- `alpha`: a valid project.
- `bad`: a project whose `project_config.yaml` sets `project_group: BAD!`.

**Section 1 — table of standalone locked-die paths.** Each row is
`label|setup|expected message|verb args`. For each row: reset the registry with
a setup function and remove any `lockd`, run the verb, then assert:
- the exit code is non-zero (`assert_exit_nonzero_rc`);
- stderr contains the expected message (`assert_contains`). This proves the run
  died at that specific `die` under the lock, not at an earlier unlocked check;
- `assert_dir_not_exists "$LOCK_DIR"`.

| label | registry setup | expected message | args |
|---|---|---|---|
| update, empty registry | header-only `projects:` | `No registered projects.` | `update alpha $ALPHA_ROOT` |
| update, unknown name | alpha | `Project 'ghost' is not registered.` | `update ghost $ALPHA_ROOT` |
| group set, unknown | alpha | `Project 'ghost' is not registered.` | `group set ghost g1` |
| group unset, unknown | alpha | `Project 'ghost' is not registered.` | `group unset ghost` |
| group rename, no member | alpha | `No registered project has group 'nope'.` | `group rename nope g2` |
| add, invalid config slug | alpha | `invalid project.project_group 'BAD!'` | `add $BAD_ROOT` |
| group sync, invalid config slug | alpha + `bad` with no group | `invalid project.project_group 'BAD!'` | `group sync` |

Every row also asserts that the registry bytes are unchanged (`cmp` against a
copy taken before the run). This catches a die that fired after the write.

**Section 2 — doctor subshell, end to end** (the case the task singled out).
Use the FIFO pattern from section 2 of the sibling test:
- The registry holds `alpha` (OK) plus two stale entries, `stale1` and `stale2`,
  both pointing at missing paths.
- Run `doctor < fifo 2> err &`, then `exec 3> fifo`, and send `u`.
- Poll up to 10 s for `New path:` on stderr. Then rewrite the registry without
  `stale1`, keeping `alpha` and `stale2`, and send `$ALPHA_ROOT`. `cmd_update`
  now runs inside doctor's subshell, acquires the lock (recorded pid = the live
  doctor), and dies with "Project 'stale1' is not registered.".
- Send `p` for `stale2`. This runs `cmd_remove --force` in the doctor's own
  shell. If the subshell had leaked the lock, this acquire would wait 10 s and
  `die`, and doctor would exit non-zero.
- Assert:
  - doctor exits 0;
  - stderr contains `Project 'stale1' is not registered.` and
    `Update failed - entry left as-is.`;
  - output contains `Removed stale2`;
  - the registry no longer names `stale2`;
  - `LOCK_DIR` is absent.
- On a prompt timeout: record a FAIL, then kill and wait for the doctor process
  (same shape as the sibling test).

**Section 3 — positive control:** `group set alpha g1` succeeds, the registry
shows `project_group: g1`, and the lock is absent. This shows the fixtures can
reach the locked section on the success path.

Then a summary footer identical to the sibling test's.

## Verification

1. `bash tests/test_projects_lock_released_on_die.sh` — all assertions PASS.
2. **Mutant proof (red-capable):** copy `.aitask-scripts/` and `tests/` into a
   scratch root. In the copy, delete the `trap "registry_lock_release '$dir'" EXIT`
   line in `lib/registry_lock.sh` and run the copied test. Expect FAILs on every
   section 1 row's lock assertion. Also expect the section 2 doctor assertions to
   fail: doctor exits non-zero after the ~10 s acquire timeout, and `Removed
   stale2` is missing. Real tree untouched.
3. Regression: `bash tests/test_projects_unreadable_registry.sh`,
   `bash tests/test_aitask_projects_doctor.sh`, `bash tests/test_aitask_projects_update.sh`,
   `bash tests/test_registry_lock.sh`.
4. `shellcheck .aitask-scripts/aitask_projects.sh tests/test_projects_lock_released_on_die.sh`.

## Step 9 (Post-Implementation)

Current-branch mode: commit the code change (`bug: … (t2164)`), commit the plan via
`aitask_task_commit.sh`, then archive per task-workflow Step 9.

## Risk

### Code-health risk: low
None identified. The change is a comment plus one new self-contained test file
using the existing scaffold and helpers. No runtime code changes.

### Goal-achievement risk: low
- The task's suggested fix (explicit releases) is deliberately not implemented,
  because measurement showed the EXIT trap already releases the lock on every
  listed path, including the doctor subshell. The task's actual concern, a lock
  left behind, is resolved by pinning the existing release with a test that the
  mutant proves can go red. · severity: low · → mitigation: none needed
  (the mutant proof in Verification step 2 is the evidence)

## Post-Review Changes

### Change Request 1 (2026-10-29 21:20)
- **Requested by user:** `read -r -a args` in the section-1 case loop split the flattened command string on whitespace, including whitespace inside `ALPHA_ROOT` / `BAD_ROOT`; under a `TMPDIR` containing a space the two `update` rows and the `add` row died at the earlier "Path does not exist" check instead of the locked die (reviewer reproduced 35/38).
- **Changes made:** the case table now carries `@ALPHA@` / `@BAD@` placeholders, substituted per element after the split, so each path stays one argument. Verified 38/38 with the default `TMPDIR` and with `TMPDIR` containing a space; the trap-removed mutant still fails 11/38 under the spaced `TMPDIR`, with every row still matching its locked-section message.
- **Files affected:** `tests/test_projects_lock_released_on_die.sh`

## Final Implementation Notes
- **Actual work done:** Measured first: every `die` the task listed (cmd_update ×2, set_registry_group via group set/unset, rename_registry_group, cmd_add invalid config slug, group sync invalid config slug) already releases `projects.yaml.lockd`, because `registry_lock_acquire` installs `trap "registry_lock_release '$dir'" EXIT` and `die` calls `exit 1`. The doctor case: the lock records the doctor's own live pid (`$$`, not the subshell's `BASHPID`), so a leak there would never be stale-reclaimed — but the subshell's own EXIT trap releases it. Shipped a regression test (`tests/test_projects_lock_released_on_die.sh`, 38 assertions: the seven locked-die rows, an end-to-end doctor run via FIFO, a positive control) and a comment above `registry_lock_or_die` in `aitask_projects.sh`. No release mechanics changed.
- **Deviations from plan:** None beyond Change Request 1 (placeholder substitution in the case table so whitespace in `TMPDIR` cannot split paths).
- **Issues encountered:** The first mutant attempt used a grep/sed pattern that did not match the trap line, so that run was unmutated and passed; redone with a fixed-string match by line number. The real mutant (trap line deleted in a scratch copy) fails 11/38: all seven lock assertions plus four doctor assertions — doctor waits out the ~10 s acquire on the leaked live-pid lock and exits 1. That confirms the doctor stall the task predicted would happen if the trap were ever lost.
- **Key decisions:** Did not add explicit `registry_lock_release` calls or a `die_locked` helper — they would duplicate the trap's release. `load_registry_or_die --locked` keeps its explicit release (harmless; out of scope). The test file is mode 644, matching its sibling.
- **Upstream defects identified:**
  - `tests/test_projects_unreadable_registry.sh:121-123` — the VERBS table flattens `$ALPHA_ROOT` / `$BETA_ROOT` into a space-split argline (`read -r -a args`), so under a `TMPDIR` containing whitespace the `add` and `update` rows die at the earlier "Path does not exist" check instead of the unreadable-registry read; fails loud (assert_contains "Cannot read…" misses), not silent. Same defect class the reviewer caught in this task's new test.

## Verification results
- `bash tests/test_projects_lock_released_on_die.sh` → 38/38 (default TMPDIR and TMPDIR with a space).
- Mutant (trap line removed in scratch copy) → 27/38, 11 failures as predicted; every row still matches its locked-section message.
- `test_projects_unreadable_registry` 145/145, `test_aitask_projects_doctor` 26/26, `test_aitask_projects_update` 14/14, `test_aitask_projects_remove` 11/11, `test_registry_lock` 51/51, `test_projects_cmd` 42/42, `test_registry_concurrency` 3/3.
- shellcheck: only SC1091 infos (unfollowed sources), as in sibling files.
