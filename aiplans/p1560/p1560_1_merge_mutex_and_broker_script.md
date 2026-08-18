---
Task: t1560_1_merge_mutex_and_broker_script.md
Parent Task: aitasks/t1560_serialize_step9_merge_across_concurrent_tasks.md
Sibling Tasks: aitasks/t1560/t1560_2_wire_step9_across_rendered_surfaces.md, aitasks/t1560/t1560_3_document_merge_mutex_and_audit_merge_paths.md, aitasks/t1560/t1560_4_manual_verification_serialize_step9_merge.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-18 22:10
---

# t1560_1 — Merge mutex + broker script (plan re-verified)

## Context

Step 9's end-of-task merge is the only mutating operation in the aitasks
pipeline with **zero serialization**. It runs in the *shared repo root*, so every
concurrently-merging task drives one HEAD, one index and one working tree. The
existing pre-flight cannot detect the race by design — it deliberately permits
"the current tree is already on the output branch", which is exactly the state
both racing agents are in. The most damaging outcome is not corruption but
**misattributed content**: while A waits for a human on a conflict, B merges and
absorbs A's partially-resolved work.

`aiplans/p1560_serialize_step9_merge_across_concurrent_tasks.md` is the design of
record. Three decisions were settled with the user before planning and are **not
re-litigated here**: parameterize `lib/stale_lock.sh` rather than fork it; hold
the mutex through verification and cleanup; decompose into three children.

This child ships the whole mechanism and is provable end-to-end **without
touching a single skill file** (that is t1560_2). A plan already existed; this
pass **re-verified it against the current codebase** and found one design change
and several corrections, recorded below.

---

## Verification outcome

The approach is sound and unchanged. The seams the plan depends on all exist and
behave as described. Confirmed accurate: `stale_lock.sh:207` (the `.gc` guard is
released *inside* `stale_lock_acquire`, which is what forces the publish-fn
seam); `stale_lock.sh:266-275` (release re-reads `owner` under the guard);
`pid_anchor.sh:224` `lock_anchor_is_self` is a literal pid+token+kind comparison,
not a liveness verdict.

### Change 1 (material) — `cleanup` must delegate, not hand-roll

The plan prescribes `git worktree remove` → `git worktree prune` → `git branch -d`
in "the `task-abort.md:57-88` shape". **That shape no longer exists.** t1548
(landed 2026-08-18) collapsed it into `.aitask-scripts/aitask_task_worktree.sh`,
now "the single canonical classifier for where this task's worktree actually
lives". Step 9 is one line (`SKILL.md:843`, `remove <task_name> --strict`) and
task-abort uses `remove <task_name> --force`. Its header contract **forbids**
`git worktree prune` (repo-global — it would discard administrative metadata for
unrelated worktrees) and `git branch -D`.

So the plan's sequence would both reimplement a canonical seam and run a `prune`
that seam exists to prevent. `cleanup` instead does its authorization and
`TARGET_MISMATCH` checks, then delegates, mapping the helper's three-line
contract onto broker verdicts:

| helper result | broker verdict |
|---|---|
| rc 0, third line `CLEAN` | `CLEANED` |
| rc 1, `PRESERVED` / `RESIDUE` | `CLEANED_PARTIAL:<remains>` from the `WORKTREE_KEPT <reason>` / `BRANCH_KEPT <reason>` lines — reservation **kept** |
| rc 2/3, empty stdout, or not exactly three well-formed lines | the cleanup **did not run** — `CLEANED_PARTIAL:cleanup_did_not_run`, reservation **kept** (never reported as success) |

Consequence: the plan's "path derived from the porcelain record, positional
argument is a fallback" requirement is **already satisfied by the helper** — that
is literally what t1548 fixed. The vestigial `[<worktree_path>]` positional is
therefore **dropped** from the `cleanup` signature.

### Change 2 (material) — `merge_lock.sh` must NOT copy registry_lock's EXIT trap

`registry_lock_acquire` installs `trap "registry_lock_release '$dir'" EXIT`
*inside acquire* (`registry_lock.sh:108-114`) and clobbers any pre-existing EXIT
trap. The merge lock's entire purpose is to **outlive the `begin` process**.
Copying "the same shape as `registry_lock.sh`" literally would release the lock
the instant `begin` returns, silently reducing the feature to a no-op. This
becomes **boundary delta #1** in `merge_lock.sh`'s header.

`registry_lock.sh`'s seconds→attempts conversion (`_REGISTRY_LOCK_ATTEMPTS_PER_SEC=20`,
sleep `0.05`, floor of 2, re-arm from remaining time) *is* the right thing to copy
for `--wait-secs` — but copied, not called.

### Change 3 — the identity seam has two substitution sites, not one

`$$` appears three times in the publish block: `:202` (token prefix), `:203` (the
`pid` write), `:205` (the read-back comparison). Overriding only the write makes
the read-back at `:205` compare the anchor pid against `$$`, always fail, and
take the partial-publish unwind path — **every acquire would fail closed**. The
seam value must be used at **both `:203` and `:205`**; `:202`'s token prefix stays
`$$` (token uniqueness is per-process; embedding a shared anchor pid weakens it).

### Change 4 — test-fixture assumptions that do not hold

- **`tests/lib/proc_fixtures.sh` has no live/anchored-process fixture.** It
  provides exactly one function, `dead_pid_fixture()`, and its comments hand the
  live case back to the caller. Case 4's live anchor must be hand-rolled
  (`sleep 120 &` + recorded PID + trap kill), following
  `test_gate_lock_single_winner.sh:76-82`.
- **The self-anchor triple is memoized process-wide** (`pid_anchor.sh:191-202`),
  cached *even when UNKNOWN*. Flipping `AIT_AGENT_PID` and re-calling in the same
  shell changes nothing. Every "different session" case (8, 8b, 8c) must invoke
  the broker as a **separate process** with the differing anchor in its
  environment — never by re-exporting in-shell.
- `test_gate_lock_single_winner.sh` keeps all asserts at top level (plain
  `PASS/FAIL/TOTAL`, no `assert_counters_init`); only the *invocation* is in a
  subshell. Follow that, or opt into the file-backed counters explicitly —
  otherwise failures inside `( … )` vanish and the file exits 0.

### Change 5 (material) — `AITASKS_LOCK_DIR` cannot gate the test-only seams

The plan honours `AIT_MERGE_LOCK_DISABLED` and `AIT_MERGE_BROKER_HOOK` "only when
`AITASKS_LOCK_DIR` is set", treating that as proof of a test environment. It is
not. `stale_lock.sh:39-42` documents it as a **deployment** seam:

> The per-UID base means two DIFFERENT users sharing one checkout do not
> serialize against each other by default … Point `AITASKS_LOCK_DIR` at an
> admin-created shared base for that setup.

That is precisely the multi-user shared-checkout deployment where merge
serialization matters most — and there, a leaked `AIT_MERGE_LOCK_DISABLED=1` in a
shell profile or inherited environment would silently disable the mutex, or an
inherited `AIT_MERGE_BROKER_HOOK` would execute inside the critical section.

**Gate instead on a marker file that production configuration cannot satisfy:**
the seams are honoured only when `<lock_base>/.ait_merge_test_seams` exists as a
regular file, where `<lock_base>` is the resolved parent of `ait_lock_dir merge`.
An admin creating a shared lock base has no reason to create it and no
documentation tells them to; the broker header states plainly that it must never
exist in a real lock base. Enabling a seam therefore requires a deliberate
filesystem action inside a directory the operator owns — an environment variable
alone can never do it. Every activation still warns on stderr.

`AITASKS_LOCK_DIR` is dropped as a precondition entirely (it may remain
incidentally set). **Discriminating negative test:** with `AITASKS_LOCK_DIR` set
and the marker **absent**, `AIT_MERGE_LOCK_DISABLED=1` must **not** disable the
acquire — the case is production-reachable exactly as the header describes.

### Change 6 (material) — `force-release` must act under the `.gc` guard

The plan's `force-release` inspects the holder, repairs the tree, then removes the
lock dir "bypassing the owner-token check" — with no guard across those three
steps. That window is reachable: `_stale_lock_reclaim_under_gc` reclaims a `dead`
holder, so a concurrent `begin` can reclaim and republish between our liveness
verdict and our `rm -rf`. The consequences are worse than a lost lock — the
repair (`git merge --abort` / `git reset --hard`) would run against a tree the new
holder is actively merging into, and the delete would remove a **fresh live
reservation**.

`stale_lock.sh` invariant 1 already states the rule this violates: *all*
lock-directory mutations are serialized by the `.gc` guard, so a staleness verdict
is always acted on in the same guard section it was formed in. `force-release` is
a lock-directory mutation formed from a staleness verdict; it must obey it.

Add a fourth, purely additive export to `stale_lock.sh`:

```
stale_lock_guarded_section <lock_dir> <fn> [<max_tries>]
```

It takes `.gc` with the same bounded `mkdir` wait `stale_lock_release` uses
(40 tries × `0.05`s), calls `<fn> <lock_dir>`, releases the guard, and fails if
the guard could not be taken or could not be released. No existing caller touches
it, so the pre-phase characterization diff must still be empty.

#### Two reads, both inside the `--yes` process

The dry-run and `--yes` are **separate invocations** and the signature carries no
snapshot, so "compare against what the dry-run reported" is not implementable as
written — an implementation would compare against nothing. Define the comparison
concretely, as two reads **within the `--yes` process**:

- **Read 1 (the inspected snapshot)** — taken *before* the guard, reading exactly
  the fields the dry-run prints: `task_id`, `anchor_pid`, `anchor_token`,
  `anchor_kind`, `acquired_at`, plus the derived liveness verdict.
- **Read 2 (the authoritative snapshot)** — taken *after* `.gc` is held, over the
  same fields.

`--yes` then acts only when both agree:

- Read 1 ≠ Read 2 → `HOLDER_CHANGED:<new_task>`, nothing repaired, nothing
  deleted (the guard is released normally).
- Read 2's liveness is `alive` → `REFUSED_LIVE_HOLDER:<task>:<pid>`, nothing
  touched.
- Read 2 finds no lock dir → `NOT_HELD`, nothing touched.

This closes the reclaim window *inside our own run*. It cannot close the gap
between the human's dry-run and their `--yes` — nothing in a stateless CLI can,
without carrying the snapshot across. So the dry-run additionally prints a
**holder token** (a digest over the Read-1 fields) and the exact copy-safe command
to act on it, and `--yes` accepts an optional `--expect <holder_token>`: when
given, a mismatch against Read 2 is `HOLDER_CHANGED:<new_task>` even if Reads 1
and 2 agree. Omitting it keeps today's ergonomics; supplying it is what makes
"force-release exactly the holder I inspected" expressible.

#### Interruption inside the guarded section

The guard is held across a git command rather than a few file ops, so the window
is long enough for a human to interrupt manual recovery — and `.gc` is the
**global** merge lock's guard, so leaking it wedges every future merge in the
repo, not one task. Both signal classes need a defined outcome:

- **Catchable (INT / TERM / HUP)** — `stale_lock_guarded_section` installs a trap
  for the duration of the section that **releases `.gc`** and returns non-zero
  (`INTERRUPTED:guard_released`). This is safe precisely because deletion is the
  *last* step: at interrupt time the lock dir is still present with its original
  holder, so releasing the guard restores the pre-`force-release` state. The tree
  may be half-repaired — which is the state force-release already exists to fix,
  and a re-run resumes from it.
- **The trap is saved and restored, never merely removed.** This is a shared
  library export, and `stale_lock.sh` installs no traps today, so stripping the
  caller's handlers would silently break their cleanup — the same defect as
  `registry_lock.sh`'s acquire clobbering the caller's EXIT trap (Change 2), now
  on the other side of the boundary. Capture the caller's exact handlers at entry
  with `trap -p INT TERM HUP` (empty when none, `trap -- '' SIG` when ignored) and
  restore with `trap - INT TERM HUP` followed by an `eval` of the saved string on
  **every** exit path: normal return, `<fn>` failure, guard-acquire failure,
  guard-release failure, and the signal path itself. On a caught signal the
  section releases `.gc`, restores the caller's handlers, and then **re-raises**
  the signal — a section must not swallow a signal the caller was prepared to
  handle.
- **The deletion step itself** is masked (`trap '' INT TERM HUP`) — it is a few
  file ops, back to the microsecond-scale window the guard was designed for, and
  being interrupted between "lock dir removed" and "guard released" is the one
  ordering that strands a guard over no lock. That mask saves and restores the
  **section's own** handler, and is lifted before the section-exit restore, so the
  two levels never cross.
- **Uncatchable (KILL, power loss)** — the guard leaks; this is invariant 2's
  documented, deliberate behaviour (guards are never auto-stolen). The recovery is
  the one already published: `stale_lock_describe` names the guard path
  ("stale-reclaim guard … present — remove it too if no reclaim is running"), so
  `status` surfaces it, the cure is `rmdir <lock_dir>.gc` (never `rm -rf`), and
  force-release is then re-run. Case 13 drives both rungs so the ladder is proven
  to terminate rather than described.

### Change 7 — stale citations to correct in the plan text

`:745` is blank (content at `:744`/`:746`); the merge span is **777-794**, not
778-791 (`git merge` sits at `:792`, one past the cited end); the cleanup block is
**841-851**, not 836-841. `task-abort.md`'s guarded-cleanup block is **63-110**,
not 57-88. `stale_lock.sh`'s header cites t1496 (and t1188) — **t1507 is in
`registry_lock.sh`**, not there. `:758` and `:791` are exact.

Also pin the sentinel: `AIT_PID_ANCHOR_UNKNOWN="-"` (`pid_anchor.sh:30`), with
`0` accepted as an equivalent legacy marker — `begin`'s `NO_SESSION_ANCHOR` guard
must test **both**, not just `-`.

---

## Implementation

### Step 0 — synchronize the durable plan **before any code**

`aiplans/p1560/p1560_1_merge_mutex_and_broker_script.md` is the artifact a
`POSTIMPL`/`IMPLEMENT` resume and any later audit reads — not this approval
screen. It still directs the hand-rolled `git worktree remove` → `git worktree
prune` → `git branch -d` sequence and still carries the obsolete positional
`[<worktree_path>]`, so a resumed session that trusted it would reintroduce the
repo-global prune hazard t1548 exists to prevent. Rewrite it first, and verify
each delta landed:

- §3d `cleanup`: hand-rolled teardown → delegation to
  `aitask_task_worktree.sh remove <task_name> --strict` with the three-line
  verdict mapping (Change 1); drop `[<worktree_path>]` from the signature in
  **both** the §3 usage block and §3d.
- §Step 2 adapter: add "no auto-release EXIT trap" as boundary delta #1 (Change 2).
- §Step 1 seam table: `STALE_LOCK_IDENTITY_PID` applies at the write **and** the
  read-back site (Change 3).
- §Step 4: replace the `AITASKS_LOCK_DIR` precondition with the marker-file gate
  (Change 5); add the fourth `stale_lock_guarded_section` export, the guarded
  `force-release` contract with its two in-process reads and optional
  `--expect <holder_token>`, and the interruption contract (Change 6).
- §Verification: case 0, cases 11–14, the case-2 operational limits, and the
  process-isolation requirement on cases 8(b)/(c) (Change 4).
- Citations per Change 7.

Only then write code.

### The four artifacts

Unchanged from the existing plan except as above.

**1. Three opt-in, default-off seams in `.aitask-scripts/lib/stale_lock.sh`.**
With all three unset the file behaves exactly as today, so `aitask_gate.sh`,
`aitask_create.sh` and `lib/registry_lock.sh` are untouched.

| Seam | Default | Effect |
|---|---|---|
| `STALE_LOCK_IDENTITY_PID` | `$$` | value written to `<lock_dir>/pid` **and** compared on read-back (Change 3) |
| `_STALE_LOCK_LIVENESS_FN` | unset | called as `<fn> <lock_dir>` right after `:162`'s `[[ -d … ]] || return 0`; **sole** authority on the holder verdict (exit 0 = do not displace → `return 1`; exit 1 = reclaim → verified rm), bypassing both the `kill -0` branch and the 120s tokenless-age branch |
| `STALE_LOCK_PUBLISH_FN` | unset | called as `<fn> <lock_dir>` **inside the `.gc` guard**, after the `:205-206` read-back and before the `:207` release; nonzero → the existing unwind-and-fail-closed path |

Plus one purely additive export, `stale_lock_guarded_section <lock_dir> <fn>
[<max_tries>]` (Change 6) — no existing caller touches it, so the characterization
diff must still be empty. It is the file's first trap-installing function, so its
save/restore of the caller's INT/TERM/HUP handlers is part of its contract, not an
implementation detail (case 14).

Do not relax any of the six documented invariants. Note the header's own
constraint: never call `stale_lock_acquire` inside a command substitution —
`STALE_LOCK_TOKEN` would be stranded in the subshell.

**2. `.aitask-scripts/lib/merge_lock.sh`** — the adapter. `STALE_LOCK_IDENTITY_PID`
from `get_session_anchor_pid`; liveness fn reads the recorded
`pid`/`anchor_token`/`anchor_kind` and calls `lock_holder_liveness` (`dead` →
reclaim; `alive` **or** `unknown` → never displace); publish fn writes, under the
guard and verified on read-back: `anchor_token`, `anchor_kind`, `task_id`,
`output_branch`, `task_branch`, `acquired_at`. One **global** lock per repo,
`ait_lock_dir merge` — two tasks merging into different branches still share one
HEAD, index and tree. Header carries the "deliberate boundary deltas" block, with
**no auto-release EXIT trap** as delta #1 (Change 2).

**3. `.aitask-scripts/aitask_merge_task.sh`** — the broker.

```
begin <task_id> <output_branch> <task_branch> [--wait-secs N]
finish <task_id>
abort  <task_id>
cleanup <task_id> <task_name> --task-complete
status
force-release [--abort-merge | --reset-hard] [--yes] [--expect <holder_token>]
```

Exit status is **disjoint from the verdict**: exit 0 = a verdict was produced
(including `BUSY` and `MERGE_CONFLICT`); nonzero = infrastructure failure only.
Exactly one verdict line on **stdout**; `WAITING:<holder>:<elapsed>` on **stderr**.
Critical section order: `MERGE_HEAD` residue → dirty tracked tree → pre-flight
(fully-qualified `refs/heads/`, foreign-worktree comparison against
`git rev-parse --show-toplevel`, moved verbatim) → `checkout` + `symbolic-ref`
assert → `merge`. Lock **retained** on `MERGE_OK`/`MERGE_CONFLICT`/`MERGE_FAILED`,
released on every pre-merge refusal — that retention is the fix. Bind every
user-authored branch name to a variable; never substitute the literal.

Ownership (§1a): `begin` refuses `NO_SESSION_ANCHOR` when the anchor is UNKNOWN —
the capability is required at acquire time so it exists at release time.
`finish`/`abort`/`cleanup` require task match **AND** provable session match
(`lock_anchor_is_self`); a task-id match is never sufficient alone. `abort`
branches on the **observed** state and verifies after acting, never assuming from
exit status; `ABORT_UNSAFE:<state>:<remedy_flag>` carries its own remedy flag.
`force-release` is dry-run by default, refuses a provably `alive` holder, and has
two distinct remedies — a mismatched flag is **refused** (`WRONG_REMEDY:no_merge_head`),
never attempted. Its `--yes` path runs revalidate → repair → verify → delete
inside `stale_lock_guarded_section`, re-deriving the holder rather than trusting
the dry-run (Change 6), and refuses on `HOLDER_CHANGED` or a now-`alive` holder.

**4. Test-only seams**, honoured **only** when `<lock_base>/.ait_merge_test_seams`
exists (Change 5 — never gated on `AITASKS_LOCK_DIR`, which is a production seam):
`AIT_MERGE_LOCK_DISABLED=1` (skip the acquire — makes the red proof reachable and
"the guard gates" executable) and `AIT_MERGE_BROKER_HOOK=<cmd>` (runs between
checkout and merge; tests rendezvous on FIFOs, so **no test sleeps to reproduce a
race**). Both warn on stderr whenever active.

**5. Helper whitelist — five touchpoints** for `aitask_merge_task.sh` (skill-invoked
by t1560_2): `.claude/settings.local.json` (`"Bash(./.aitask-scripts/aitask_merge_task.sh:*)"`),
`.codex/rules/default.rules` and `seed/codex_rules.default.rules`
(`prefix_rule(pattern = […], decision = "allow", justification = "Aitasks helper script")`),
`seed/claude_settings.local.json`, and `seed/opencode_config.seed.json`
(`"./.aitask-scripts/aitask_merge_task.sh *": "allow"` — space-glob, not `:*`).
`lib/merge_lock.sh` is sourced, not invoked → **none**. No `ait` subcommand.

**6. Export the verdict vocabulary** (a `--list-verdicts` verb or one delimited
comment block) so t1560_2's rendered-verdict test asserts coverage mechanically.

## Pre-phase (risk mitigations)

`characterize_stale_lock_callers` — **before any edit to `lib/stale_lock.sh`**,
capture a baseline of `test_stale_lock.sh`, `test_gate_lock_single_winner.sh`,
`test_registry_lock_single_winner.sh`, `test_parallel_child_create.sh`,
`test_task_lock.sh`; re-run and diff once the seams land. The seams are
default-off precisely so this diff is empty. A non-empty diff is a defect in the
seam, not a test to update.

`cross_process_hold_positive_control` — the **first** merge-lock test written,
before the broker's verbs are fleshed out. Process P1 acquires via `begin` and
exits; assert the lock dir still exists **after P1 is gone**, and that a second
process P2's `begin` returns `BUSY:<P1 task>`. This is the positive control for
the feature's load-bearing property (the reservation outlives its acquiring
process) and it fails loudly and unambiguously if `merge_lock.sh` inherited
`registry_lock.sh`'s self-releasing EXIT trap. Case 3 also catches that, but only
via the conflict fixture and much later in the suite.

## Post-phase (risk mitigations)

`wedge_recovery_probe` — drive the unresolvable-anchor path to a wedged merge
lock and assert `status` names the holder with its liveness verdict and
`force-release` clears it, proving the recovery ladder **terminates**.

## Risk

### Code-health risk: medium
- `lib/stale_lock.sh` is a hardened primitive with three production callers (gate-ledger appends, child-task numbering, the project/attach registry lock); adding three seams — one of which runs *inside* the `.gc` guard — risks changing behaviour on paths that are currently correct · severity: medium · → mitigation: inline pre-phase characterize_stale_lock_callers
- The adapter is modelled on `lib/registry_lock.sh`, whose `acquire` installs a self-releasing EXIT trap; copying that shape verbatim would release the merge lock the instant `begin` returns, silently reducing the feature to a no-op while single-process tests still pass · severity: high · → mitigation: inline pre-phase cross_process_hold_positive_control
- An unresolvable session anchor makes the merge lock **never** auto-reclaimable by design, so a leaked lock wedges every future merge in the repo until a human intervenes · severity: medium · → mitigation: inline post-phase wedge_recovery_probe
- The broker centralizes checkout + merge + verification + cleanup, so a bug in it breaks every task's Step 9 at once, where today the failure is per-agent and inline · severity: medium · → mitigation: TBD (covered by the enumerated test suite; no separate mitigation)
- `cleanup` now delegates to `aitask_task_worktree.sh remove --strict`, coupling broker verdicts to that helper's three-line output contract; a change there silently changes what the broker reports · severity: low · → mitigation: TBD (accepted — the alternative is reimplementing a canonical seam the helper exists to own; case 10 pins the mapping and `tests/test_task_worktree_helper.sh` pins the helper)
- `force-release` now holds the `.gc` guard across a git repair command rather than a few file ops, and `.gc` guards the **global** merge lock — so a leak wedges every future merge in the repo, not one task. Catchable signals release it, but an uncatchable kill still leaks it · severity: medium · → mitigation: TBD (accepted — the alternative is destroying a live reservation and repairing a tree another holder is merging into. The window is bounded by one git command; INT/TERM/HUP release the guard and the deletion step is signal-masked; `status` names a wedged guard and `rmdir` is the published cure. Case 13 drives both signal classes and inline post-phase wedge_recovery_probe proves the ladder terminates)
- Requiring a resolvable session anchor to `begin` is a **new hard precondition** on worktree-mode merges: an agent outside tmux with no `AIT_AGENT_PID` can no longer merge until one is supplied · severity: medium · → mitigation: TBD (accepted deliberately — the alternative is a reservation whose owner cannot be proven; `NO_SESSION_ANCHOR` names both remedies inline, and t1560_3 documents the precondition in `locks.md`)

### Goal-achievement risk: medium
- AC 1's red proof depends on a two-caller FIFO rendezvous; if the hook point is wrong the "proof" trips an earlier assertion instead of the raced merge and proves nothing · severity: medium · → mitigation: TBD (test 1n pins the boundary by naming the failing case)
- The feature is inert under this repo's own `fast` profile (`create_worktree: false`), so day-to-day use never exercises it and regressions surface only in the suite · severity: low · → mitigation: TBD (stated as a non-goal consequence; t1560_3's docs say so explicitly)

### Planned mitigations
- timing: pre-phase | name: characterize_stale_lock_callers | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: stale_lock.sh seams change existing caller behaviour | desc: Baseline the five existing lock test files before editing lib/stale_lock.sh and diff the runs after the seams land.
- timing: pre-phase | name: cross_process_hold_positive_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: an inherited self-releasing EXIT trap would silently no-op the mutex | desc: Assert a lock acquired by one process is still held after that process exits and that a second process observes BUSY.
- timing: post-phase | name: wedge_recovery_probe | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: unresolvable anchor makes the merge lock never auto-reclaimable | desc: Prove the wedged-lock recovery ladder terminates — status names the holder, force-release clears it.

## Verification

`aidocs/framework/testing_conventions.md:10,18` mandates the enumeration. Fixture
rule for every recovery assertion: mergeability is a property of the fixture, so
"the lock works again" is always proved by a **different, cleanly mergeable**
task — never by re-running the branch whose merge produced the residue. Keep
three fixture shapes: cleanly-mergeable, conflicting, unrelated-history.

| # | Case | Assertion |
|---|---|---|
| 0 | Cross-process hold (positive control, pre-phase) | P1 `begin`s and exits; the lock dir still exists after P1 is gone, and P2's `begin` returns `BUSY:<P1 task>`. Written first — guards against an inherited self-releasing EXIT trap |
| 1 | Red proof, mutex disabled | A parks between checkout and merge (FIFO hook); B merges; A resumes → A's merge commit's tree **contains B's file**. With the mutex enabled: B reports `BUSY:tA`, A's commit is clean |
| 1n | Negative control for 1 | The mutation must reach the *merge-contamination* assertion, not trip an earlier one — assert the named failing case |
| 2 | N = 51 concurrent callers | see the operational contract below the table — it is part of the case, not decoration |
| 3 | Conflict-parked reservation | A stops at `MERGE_CONFLICT`; B (separate process) does **not** enter and names A's task id; after A's `abort`, B proceeds. **Doubles as the cross-process-persistence guard for Change 2** |
| 4 | Stale-holder recovery | anchor = a hand-rolled `AIT_AGENT_PID` fixture process; killed mid-section → exactly **one** waiter reclaims. Live-anchored → never displaced; `unknown` → never displaced |
| 5 | Guard gates | removing the acquire via the documented seam makes cases 1 and 3 fail |
| 6 | Callers unchanged | the five baseline files still pass, diffed against the pre-phase capture |
| 7 | Wedge recovery terminates | unresolvable anchor → never auto-reclaimed; `status` names it; `force-release --yes` clears it. Live holder → `REFUSED_LIVE_HOLDER`, intact. `MERGE_HEAD` + no flag → `RESIDUE_PRESENT`, intact; `--abort-merge` → verified clean + released. **Both residue states separately**: unmerged-index-without-`MERGE_HEAD` → `--abort-merge` gives `WRONG_REMEDY:no_merge_head` lock **kept**, `--reset-hard --yes` reaches verified-clean and releases |
| 8 | Non-owner release refused | (a) B's `finish`/`abort`/`cleanup` vs A's lock → `NOT_HOLDER:tA`, intact, A can still `finish`. (b) same task id, caller that cannot prove its anchor → `NOT_OWNER_SESSION`. (c) same task id, provably different live session → `NOT_OWNER_SESSION`. (d) planted dir with no `task_id` → `HOLDER_INCOMPLETE`, cleared by `force-release --yes`. (e) `begin` with no anchor → `NO_SESSION_ANCHOR`, nothing locked. **(b)/(c) run as separate processes** (Change 4) |
| 8b | Non-conflict merge failure | task **U** with unrelated history → `git merge` fails before `MERGE_HEAD` → `MERGE_FAILED`; `abort` → `RELEASED_NO_MERGE` (**not** `ABORT_FAILED`). Usable-again proof from a **different** task V. Plus planted no-`MERGE_HEAD`-but-unmerged-index → `ABORT_UNSAFE`, lock **kept** |
| 8c | Verification window does not strand the lock | scripted Step-9 mimic: `begin` → injected failing verification → "release and stop" → `finish` **without** cleanup. Lock free, merge commit intact, branch + worktree still present. Re-run `begin` → `MERGE_OK` with **no new commit** |
| 9 | Publish is atomic with acquire | `STALE_LOCK_PUBLISH_FN` returning nonzero → acquire unwinds, **no** lock dir left behind, contender's next attempt succeeds |
| 11 | Test-seam gate is not production-reachable | with `AITASKS_LOCK_DIR` set (the documented admin-shared-base deployment) and the marker file **absent**, `AIT_MERGE_LOCK_DISABLED=1` does **not** disable the acquire and `AIT_MERGE_BROKER_HOOK` is **not** executed — a second caller still gets `BUSY`. With the marker present, both take effect. Pins Change 5 in both directions |
| 12 | `force-release` is atomic against a reclaim | replacement is injected **between Read 1 and the guard acquisition, inside the `--yes` process** (deterministic FIFO rendezvous at that exact point — not a sleep, and not merely "between two CLI runs"): a contender reclaims and republishes → `HOLDER_CHANGED:<new_task>`, **nothing** repaired and **nothing** deleted, and the new holder's reservation survives and can still `finish`. Variants: holder became `alive` → `REFUSED_LIVE_HOLDER`; lock gone → `NOT_HELD`; and a cross-invocation `--expect <token>` mismatch → `HOLDER_CHANGED` even when Reads 1 and 2 agree. Pins Change 6 |
| 14 | Guarded section preserves caller traps | a caller installs its own INT handler (writes a sentinel), then calls `stale_lock_guarded_section`. After a **normal** return: `trap -p INT` still shows the caller's handler verbatim, and a subsequently delivered INT **fires it** (sentinel written) — the assertion is that it fires, not merely that the string is present. Repeat for the `<fn>`-failure, guard-acquire-failure and guard-release-failure exit paths, and for a signal delivered **during** the section (guard released, caller's handler restored **and** run via the re-raise). Negative control: a caller with **no** prior handler ends with none installed, not with ours |
| 13 | Interrupted recovery terminates | (a) SIGINT delivered while the guarded repair runs → `.gc` is **gone**, the lock dir is intact with its original holder recorded, and a subsequent `force-release --yes` succeeds. (b) Uncatchable kill simulated by a planted `.gc`: `status` names the wedged guard and its path, a concurrent `begin` refuses/times out rather than corrupting, and the documented `rmdir <lock_dir>.gc` + re-run recovers. On both rungs the "usable again" proof is a `begin` from a **different, cleanly mergeable task** |
| 10 | Cleanup authorization + partial failure | no `--task-complete` → `CLEANUP_REQUIRES_COMPLETION`, branch+worktree intact, following `begin` still `MERGE_OK`. Non-owner → refused. `<task_name>` ≠ recorded `task_branch` → `TARGET_MISMATCH`. **Moved** worktree still found (via the delegated helper). Undeletable worktree / unmerged branch → `CLEANED_PARTIAL:<remains>`, reservation **still held**. Malformed/2/3 helper result → **not** reported as success |

Also: `shellcheck .aitask-scripts/aitask_merge_task.sh .aitask-scripts/lib/merge_lock.sh .aitask-scripts/lib/stale_lock.sh`

### Case 2 operational contract (N = 51)

Unbounded "retry until it works" makes the proof unreproducible and lets a failed
worker strand a reservation that silently poisons every later case in the file.
This box also runs several agents concurrently, so the budget must absorb load
without the assertion becoming a performance measurement.

- **Per caller:** `--wait-secs 120`, attempt cap **10** `begin` calls. A caller
  retries **only** on `BUSY`; any other verdict ends its loop, so a caller can
  never merge twice after a lost verdict.
- **Whole case:** a wall-clock guard of **600s** as a *guard, not an assertion* —
  on expiry the case fails with diagnostics instead of hanging. Its message must
  distinguish "exhausted the wait budget" (environment/load) from "wrong verdict"
  (defect); only the latter indicts the implementation.
- **Diagnostics:** each caller writes stdout and stderr to
  `$TMP/n51_out_$i.log` / `$TMP/n51_err_$i.log` and its exit status to
  `$TMP/n51_rc_$i` (the `test_gate_lock_single_winner.sh:107` shape). On failure
  the test prints the first three offending logs — a bare count tells you nothing
  about which caller broke.
- **Assertions:** exactly 51 `MERGE_OK`; exactly 51 merge commits on
  `<output_branch>`, carrying **51 distinct task ids**; every recorded rc is `0`;
  and **at least one** `BUSY`/`WAITING` naming a real holder task id (else the
  case is vacuous). A caller that exhausts its cap is a failure, not a permitted
  outcome.
- **Teardown (trap-installed, runs on every exit path):** kill any surviving
  worker PIDs by recorded PID — no `setsid`, no process-group kill that could
  reach the test runner — then `force-release --yes` so the lock is guaranteed
  free, then remove the fixture.
- **Post-case assertion:** `status` reports the lock **free**. Without it a leaked
  reservation from this case would make cases 3 onward fail for the wrong reason.

## Non-goals

No Step 9 / skill edits (**t1560_2**). No website docs (**t1560_3**). No fetch
added to Step 9 (**t1393**); no edit-time file-overlap advice (**t1343**/**t1344**);
no change to push behaviour.
