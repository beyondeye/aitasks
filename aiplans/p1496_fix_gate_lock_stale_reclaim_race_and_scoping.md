---
Task: t1496_fix_gate_lock_stale_reclaim_race_and_scoping.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
Output branch: main
---

# t1496 — Fix the gate-lock stale-reclaim race and lock scoping

## Context

`acquire_gate_lock` (`.aitask-scripts/aitask_gate.sh:120-156`) decides "stale"
from a `stat` of the lock dir, then `mv`s **whatever is at that path**. Between
the two, another contender can complete a full reclaim + re-`mkdir` cycle, so
the first contender moves away a *fresh, live* lock — two holders inside the
critical section (reproduced 3/25 rounds against unmodified code: lost ledger
block, or duplicate `attempt=` numbers). `mv` is atomic on the path, never on
the inode that was `stat`ed. This is a different window from t1188's (`stat`
*fails*); here `stat` *succeeds* on a dir that is then replaced.

Also in scope (task bullets 2–3):
- the lock path `/tmp/aitask_gate_lock_<key>` is neither repo-scoped nor
  env-overridable — two checkouts on one machine share a namespace;
- `tests/test_parallel_child_create.sh` hard-codes `/tmp/aitask_child_lock_100`
  (the same fixed-`/tmp` collision t1485 fixed for the gate suite).

`aitask_create.sh:331-377` (`acquire_child_lock`) is a verbatim copy of the
racy reclaim — one shared helper fixes both sites.

## Design: a small shared lock helper

**NEW `.aitask-scripts/lib/stale_lock.sh`**, used by `aitask_gate.sh` and
`aitask_create.sh`. `lib/registry_lock.sh` is NOT touched (its identical latent
race becomes the spawned follow-up task; see Risk).

### Invariants (the contract — everything else is implementation detail)

1. **All lock-directory mutations are serialized by a `.gc` guard dir**
   (`<lock_dir>.gc`, mkdir-mutex): identity publication at acquire,
   owner-checked release, and reclaim observation+destruction all happen while
   holding `.gc`. Only the protected application operation runs outside it.
   This is what kills the defect: a staleness verdict can no longer be acted
   on after another contender has reclaimed and republished, because both
   verdict and destruction sit in one `.gc` section and every other mutation
   waits on it.
2. **`.gc` is fail-closed and never automatically stolen.** A leaked `.gc`
   (kill inside its few-file-op section) wedges that one lock until removed by
   hand; the acquire-exhaustion error names it. No age/PID heuristics on `.gc`.
3. **A live PID is never displaced; a dead PID may be reclaimed.** Liveness =
   `kill -0` (EPERM counts as alive). A lock dir with no readable PID file is
   legacy/foreign: reclaimed only when older than the stale window (120s),
   else waited on. PID reuse can conservatively leave an orphaned lock —
   documented limitation, manual recovery via the error hint. No start-time
   comparison, no locale machinery, no PID-reuse recovery.
4. **Release requires an unguessable owner token.** Acquire writes a random
   token file and returns the token via an explicit output variable; release
   takes it as an explicit argument and removes the lock only on match. No
   hidden module state; the two current callers each hold one lock at a time
   (documented).
5. **Lock paths are per-user, per-repository, and test-overridable.**
   `ait_lock_dir <name>` → `$AITASKS_LOCK_DIR/<name>` when set (the documented
   test seam), else `${TMPDIR:-/tmp}/aitask-locks-<uid>-<cksum-of-repo-root>`
   (repo root = the lib's own location, never ambient cwd). The base is
   created `(umask 077; mkdir)` — atomically owner-only — and accepted on
   EEXIST only as a non-symlink dir owned by the current uid; anything else
   dies. Never chmod a pre-existing path.
6. **Cleanup failures are propagated.** Removals are verified (`rm` + path
   absent); a retained lock or guard is warned about and returned as failure —
   never reported as success. Explicit release call sites in both callers
   propagate the status; the EXIT-trap handler captures the incoming `$?`,
   releases errexit-safely, preserves a nonzero status, and flips 0→1 only
   when release itself failed.

### API

```
stale_lock_acquire <lock_dir> <retries> <sleep> <label>   # sets STALE_LOCK_TOKEN
stale_lock_release <lock_dir> <token>
ait_lock_dir <name>                                        # echoes resolved path
```

- Acquire loop: bounded attempts (every failed iteration counts — a reclaim
  stream cannot loop past the budget; a successful reclaim skips only the
  sleep). On exhaustion returns 1 having touched nothing; callers keep their
  existing `die` texts (`Failed to acquire gate append lock for <key> after 20
  attempts` — pinned by characterization Test 2a) extended with a recovery
  hint naming the lock dir, the recorded holder PID, and any `.gc` dir.
- All internals that can return routine nonzero run in explicit conditional
  constructs — both callers are `set -euo pipefail`.
- Callers wrap it: `acquire_gate_lock`/`release_gate_lock` (20×0.3s),
  `acquire_child_lock`/`release_child_lock` (20×0.5s); call sites and trap
  shapes otherwise unchanged.

### Documented limitations (lib header)

- Rolling upgrade: an old-code process running during the upgrade uses the old
  `/tmp` path and is invisible to the new lock — not handled here.
- Per-UID base: two *different users* sharing one checkout no longer serialize
  by default (the old world-writable `/tmp` lock did, unsafely); point
  `AITASKS_LOCK_DIR` at an admin-created shared base for that setup.
- One lock at a time per caller process; acquire/release from the main script
  process (both callers comply).

## Files

### Pre-phase (risk mitigations)

1. `[negative_control_single_winner]` Before any source edit, **record a
   focused reproduction of the defect against HEAD**: run the deterministic
   distinguishing case — a backdated (>120s) lock dir at HEAD's
   `/tmp/aitask_gate_lock_<key>` path whose holder is a live background
   process — and show `append` steals it (HEAD judges by mtime alone). Paste
   the observed output into this plan. This is a one-off recorded control, not
   a permanent dual-layout test.

   **RECORDED (2026-08-13, HEAD 065ab5a0c, `aitask_gate.sh` clean vs HEAD):**

   ```
   === holder pid 2516783 alive: yes
   === running append against the held lock (HEAD code) ...
   Warning: Removing stale gate lock for 92516778 (age: 208774006s)
   > **✅ gate:tests_pass** run=2026-08-13T06:46:46Z status=pass attempt=1
   === append rc=0
   === holder still alive: yes
   === holder's lock dir survived: NO — STOLEN
   === ledger blocks written: 1
   NEGCTRL: RED — live holder's lock was stolen and append proceeded (defect present)
   ```

   Deterministic RED: HEAD displaced a live holder's lock purely on mtime and
   proceeded into the critical section. The fixed code must fail this exact
   construction closed (exhaust + holder's dir intact).
2. `[enumerate_scaffold_startup_deps]` Before adding the startup `source`
   line, enumerate every fixture copying `aitask_gate.sh` or
   `aitask_create.sh` and confirm each builds `.aitask-scripts/lib/` via
   `setup_fake_aitask_repo`; any hand-rolled `cp` list found gets its own
   `stale_lock.sh` line in the same commit. Record the list.

   **RECORDED (2026-08-13):** 23 fixtures copy `aitask_create.sh` and/or
   `aitask_gate.sh` (`test_anchor_create`, `test_anchor_update`,
   `test_characterize_batch_label_frontmatter`, `test_archive_verification_gate`,
   `test_archive_carryover_anchor`, `test_auto_merge_file_ref`,
   `test_draft_finalize`, `test_gate_guarded_archival`,
   `test_create_project_flag`, `test_create_silent_stdout`,
   `test_issue_import_contributor`, `test_atomic_task_file_writes`,
   `test_file_references`, `test_followup_kind_roundtrip`, `test_label_autoadd`,
   `test_create_manual_verification`, `test_create_manual_verification_gates`,
   `test_update_risk`, `test_pr_contributor_metadata`,
   `test_parallel_child_create`, `test_verifies_field`,
   `test_verification_followup`, `test_verification_followup_anchor`) — **every
   one** builds its lib tree via `setup_fake_aitask_repo`; their extra `cp
   lib/` lines are additions on top of it, so the single scaffold `cp` line
   covers all. The remaining gate tests run `$PROJECT_DIR/.aitask-scripts/...`
   in place (real lib present). No hand-rolled list needs patching.

### Implementation

1. **NEW `.aitask-scripts/lib/stale_lock.sh`** — the helper above. Depends
   only on `warn` from `lib/terminal_compat.sh` (already sourced first by both
   callers).
2. **`.aitask-scripts/aitask_gate.sh`** — source the lib at startup; reduce
   `acquire_gate_lock`/`release_gate_lock` to wrappers; propagate explicit
   release failures; EXIT-trap handler per invariant 6.
3. **`.aitask-scripts/aitask_create.sh`** — same for the child lock.
4. **`tests/lib/test_scaffold.sh`** — add the `cp` line for `stale_lock.sh`
   (source-on-startup ↔ test-scaffold rule), with the customary why-comment.
5. **`tests/test_parallel_child_create.sh`** (task bullet 3) — export
   `AITASKS_LOCK_DIR="$(mktemp -d)"` at the top; derive the child-lock path
   from it at l.76-77, 180-182, 214, 220. No hard-coded `/tmp` path remains.
6. **`tests/test_gate_lock_characterization.sh`** — re-base `GATE_LOCK_BASE`
   onto the `AITASKS_LOCK_DIR` seam and correct the header notes that say no
   seam exists; `key_for_id()` and the t635_30 flip contract keep their shape;
   Test 5 additionally asserts the die's exit status survives the new trap
   handler.
7. **NEW `tests/test_stale_lock.sh`** — unit tests of the invariants, new
   layout only (sourcing the lib directly).
8. **NEW `tests/test_gate_lock_single_winner.sh`** — production concurrency
   integration test through `aitask_gate.sh append`, new layout only.
9. **`aidocs/framework/shell_conventions.md`** — short subsection: the helper
   is the sanctioned mutex for new `/tmp`-style locks; reclaim policy;
   `AITASKS_LOCK_DIR` seam.

### Post-phase (risk mitigations)

1. `[wedged_lock_recovery_hint]` The exhaustion `die` in both callers carries
   the recovery hint (lock dir, holder PID when readable, `.gc` dir when
   present) after the byte-identical pinned prefix; pinned by a unit test.

## Acceptance tests

`tests/test_stale_lock.sh` (unit, lib-level):
- acquire/release round-trip; token returned via `STALE_LOCK_TOKEN` and
  required by release (wrong/missing token → lock left intact).
- live-PID holder never displaced (acquire fails, dir intact); dead-PID holder
  reclaimed with warn; tokenless fresh → wait; tokenless old → reclaimed.
- `.gc` pre-existing → never removed; blocks reclaim and release; both return
  failure with the lock retained and warned.
- `AITASKS_LOCK_DIR` honoured; default base per-uid+repo (two roots → two
  bases); symlink at base path → die, target untouched; fresh base is 0700.
- cleanup propagation: an `rm` PATH shim failing for the lock/guard path →
  acquire/release return failure, never success with a retained dir.
- errexit harness: contention→success and reclaim cycles driven from a
  `set -euo pipefail` script complete without spurious termination.
- exhaustion die-hint carries lock dir + PID (+ `.gc` when present) after the
  pinned prefix.

`tests/test_gate_lock_single_winner.sh` (integration, production path):
- **Live-holder case (the regression pin):** backdated lock at the resolved
  path with a live holder PID → `append` must exhaust and fail, holder's lock
  intact. (This is the behavior HEAD provably lacked — pre-phase record.)
- **Concurrency:** K concurrent `append`s against one tokenless pre-staled
  lock → exactly K ledger blocks, `attempt=1..K` each exactly once, exactly
  one reclaim warn, no lock dir left behind.

Plus: `bash tests/test_gate_lock_characterization.sh` (all pass; 2a/6/6b/7
load-bearing), `bash tests/test_parallel_child_create.sh` twice concurrently
(bullet 3's own acceptance), the scaffold blast-radius set
(`test_gate_ledger.sh`, `test_gate_guarded_archival.sh`,
`test_create_manual_verification.sh`, `test_create_project_flag.sh`, …), and
`shellcheck` on the three touched scripts.

## Final Implementation Notes

- **Actual work done:** As planned, plus one review-driven correction (see
  Post-Review Changes). NEW `.aitask-scripts/lib/stale_lock.sh` (guarded
  single-winner mutex: `.gc` serializes publish/release/reclaim; live PID
  never displaced; owner-token release via `STALE_LOCK_TOKEN`; per-uid+repo
  base with `AITASKS_LOCK_DIR` seam; verified removals). `aitask_gate.sh` and
  `aitask_create.sh` reduced to wrappers with pinned die texts + recovery
  hints, `*_checked` explicit releases, and status-preserving EXIT-trap
  handlers. Bullet 3: `test_parallel_child_create.sh` on the seam (concurrent
  double-run 24/24+24/24). `test_gate_lock_characterization.sh` rebased onto
  the seam (47/47; Test 5 now also pins die-status preservation). NEW
  `tests/test_stale_lock.sh` (79/79) and
  `tests/test_gate_lock_single_winner.sh` (17/17, stable ×5). Scaffold `cp`
  line + `shell_conventions.md` subsection and baseline-list update.
- **Deviations from plan:** (1) Guard release is a bare authoritative `rmdir`,
  not the rm+absence-check shape — the absence check misreads a contender's
  instant guard replacement as retention (review finding, see Post-Review
  Changes). (2) `tests/test_atomic_task_file_writes.sh` needed a fixture
  retarget: its TMPDIR-residue counter now exempts the (empty) persistent
  `aitask-locks-*` base while still counting any lock leaked inside it.
  (3) No allowlist touchpoints: the lib is sourced, never skill-invoked
  (per `aitasks_extension_points.md`).
- **Issues encountered:** Capturing `stale_lock_acquire` via `$(...)` strands
  `STALE_LOCK_TOKEN` in the subshell — surfaced by the unit tests' own
  "not owner" warnings; documented as a lib-header constraint and the tests
  switched to stderr-to-file capture. Test shim `case` patterns initially
  required a leading space that single-arg `rmdir` calls never have.
- **Key decisions:** Fail-closed everywhere (never steal a live holder; never
  auto-break `.gc`; publish unwind only under a genuinely held guard);
  pid-liveness + random token instead of start-time identity (PID reuse =
  documented orphaned-lock limitation); per-uid 0700 base, cross-user sharing
  via an admin-provided `AITASKS_LOCK_DIR` only.
- **Upstream defects identified:** `.aitask-scripts/lib/registry_lock.sh:52-58
  — same observe-then-destruct steal shape this task fixed (holder observed
  dead, then `mv` acts on whatever is at the path); latent two-holder window
  under contention for `ait projects` / `ait attach`. Already covered: the
  Step 8d "after" mitigation `convert_registry_lock_to_shared_core` creates
  the follow-up task for exactly this — do not double-create from this bullet.

## Post-Review Changes

### Change Request 1 (2026-08-13 10:20)
- **Requested by user:** Step-8 review surfaced two CONFIRMED findings:
  (1) guard release used `rm -rf` + absence check, so a contender's *instant
  replacement* of the freed guard was misread as "our guard retained" — the
  acquire path then unwound its own valid published lock, outside any held
  guard; (2) the unit tests' cleanup shims matched only the lock path, never
  `.gc`, leaving the guard-release behavior untested.
- **Changes made:** Guard release is now `_stale_lock_gc_release` — a bare
  `rmdir` whose own exit status is authoritative (success = we removed our
  guard, regardless of instant recreation; guard dirs are always empty, so a
  failure is genuine retention and means we still hold the guard, which is
  what legitimizes the fail-closed unwind). `_stale_lock_rm_verified` is
  documented as lock-dir-only-under-guard. Added three deterministic unit
  cases: acquire-side guard-replacement (shimmed `rmdir` real-removes,
  instantly recreates, returns real status — RED under the old absence check),
  release-side replacement, and genuine guard-`rmdir` failure on the publish
  path (fail closed, lock unwound under the held guard, guard named in the
  warn). Suite now 79/79; integration 17/17, characterization 47/47,
  parallel-create 24/24 re-verified.
- **Files affected:** `.aitask-scripts/lib/stale_lock.sh`,
  `tests/test_stale_lock.sh`.

## Risk

### Code-health risk: medium
- Load-bearing mutex for every gate append and child creation; a defect here
  turns a rare race common. · severity: high · → mitigation: inline pre-phase
  negative_control_single_winner
- Live holders are no longer displaced after 120s, so a hung agent wedges that
  key until manual cleanup (was: unsafe self-heal). · severity: medium ·
  → mitigation: inline post-phase wedged_lock_recovery_hint
- Startup `source` in two widely-scaffolded scripts can break hand-rolled test
  fixtures with a bare "No such file or directory". · severity: medium ·
  → mitigation: inline pre-phase enumerate_scaffold_startup_deps
- A second mutex lib lands beside `registry_lock.sh`, which keeps the same
  latent `mv` race — deliberate blast-radius containment, debt until
  converted. · severity: low · → mitigation: convert_registry_lock_to_shared_core

### Goal-achievement risk: low
- The defect is a 3/25 timing race; a test green on unfixed code proves
  nothing. · severity: high · → mitigation: inline pre-phase
  negative_control_single_winner (recorded RED reproduction before any edit)
- PID reuse / rolling upgrade are documented limitations, not handled — a
  reviewer expecting full coverage would judge the goal unmet. · severity: low
  · → mitigation: documented in the lib header

### Planned mitigations
- timing: pre-phase | name: negative_control_single_winner | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement "race test could prove nothing" + code-health "load-bearing mutex" | desc: Record a focused RED reproduction of the stale-reclaim defect against unmodified HEAD before any source edit.
- timing: pre-phase | name: enumerate_scaffold_startup_deps | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "startup source breaks hand-rolled scaffolds" | desc: Enumerate fixtures copying aitask_gate.sh/aitask_create.sh and patch any hand-rolled lib list in the same commit as the new source line.
- timing: post-phase | name: wedged_lock_recovery_hint | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "no more self-heal for live holders" | desc: Exhaustion die names lock dir, holder PID, and any .gc dir after the pinned message prefix, with a test.
- timing: after | name: convert_registry_lock_to_shared_core | type: refactor | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: code-health "second mutex lib beside registry_lock.sh" | desc: Convert lib/registry_lock.sh onto the shared stale_lock core, closing its identical latent mv race, revalidating ait projects bootstrap bursts and ait attach transactions.
