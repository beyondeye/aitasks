---
Task: t1466_lock_acquire_has_no_liveness_gate_so_a_live_holder_is_silent.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1466 — Gate lock acquisition on holder liveness

## Context

`aitask_lock.sh::lock_task()` enters its "idempotent refresh" branch on an
**email match alone** (line 191). It reads the prior lock's PID-anchor fields
only to decorate the signals `aitask_pick_own.sh` emits *afterwards* — they
never gate the acquisition. For the multi-pane, single-user setup this project
encourages, the mutex therefore excludes nothing: whoever claims last wins,
silently. Observed live — two `/aitask-pick` sessions both owned t1427_5 and
duplicated its verification work.

t1465 (landed, `8c2e9085d`) supplied the missing discriminator: the lock's
`pid:` now names the **agent session's own process** (the tmux pane), and
`lock_holder_liveness()` reports three honest states (`alive` / `dead` /
`unknown`). This task consumes that discriminator on the **acquire** path.

The idempotent same-email refresh is intentional and must keep working — normal
resume, crash recovery, and multi-PC handoff all depend on it. What is missing
is the distinction between a **resume** (holder gone) and a **collision**
(holder still running, or not provably gone).

Intended outcome: a same-host, same-email lock is refused at acquire time —
before any lock write, status change, or commit — unless the holder is either
*this very session* or *provably gone*.

## Design decisions

**The discriminator is the session anchor, not the email.** "A different session
by the same user" = the prior lock's `(pid, pid_starttime, pid_starttime_kind)`
triple differs from this session's. A new helper computes that once.

**Self-refresh is exempt.** When the prior anchor *is* this session's anchor,
the lock is refreshed silently exactly as today. Without this exemption the fix
would refuse the single most common path (Step 7's ownership guard, a re-pick
in the same pane, a resumed in-flight task) — every one of which would see its
own live pane process as a "live holder".

**Acquisition is deferred, not undone.** Both new outcomes refuse *before* the
lock is written, so nothing has to be given back. This is what makes remote /
headless mode safe **by construction**: `aitask-pickrem` has no `RECLAIM_*`
handling at all (verified — it proceeds on `OWNED:` and ignores every reclaim
signal), so any design that acquires first and signals afterwards is
automatically taken over in remote mode. That is why the `unknown` verdict gets
a refusal rather than a new post-claim `RECLAIM_UNVERIFIABLE:` signal.

**Four outcomes** (same host, same email, not-self):

| prior anchor verdict | acquire | outcome |
|---|---|---|
| `dead` | proceeds (unchanged) | `RECLAIM_CRASH:` |
| `alive` | **REFUSED**, exit 13 | `LOCK_LIVE_HOLDER:` |
| `unknown`, anchor recorded (numeric pid) | **REFUSED**, exit 14 | `LOCK_UNVERIFIABLE_HOLDER:` |
| `unknown`, **no** anchor (`-` / `0` / absent) | proceeds (unchanged) | `RECLAIM_STATUS:` |

The last row is the load-bearing split: a lock that never named a session has
nothing to verify, and refusing it would break every legacy lock and every
claim made outside tmux. A lock that *did* name a session but cannot be decided
is a genuinely different state — "cannot tell" — and it is the one the task
requires to stop defaulting to a silent takeover.

This costs nothing on macOS. A crashed agent's PID is *absent*, which resolves
to `dead` before any token is compared, so crash-resume still works there; and
a macOS self re-pick matches on `(pid, ps-token, kind: ps)` and is exempt. The
only macOS case reaching the `unknown` refusal is a second session whose PID
still exists — the collision case.

**Cross-host is untouched.** A PID from another machine is not comparable here,
so the gate only arms when both hostnames are non-empty, not `unknown`, and
equal — mirroring the existing `LOCK_RECLAIM` guard.

## Implementation

### 1. `.aitask-scripts/lib/pid_anchor.sh` — the self-identity seam

Add, next to `lock_holder_liveness()`:

- `_ait_current_anchor()` — memoized (`_AIT_SELF_ANCHOR_*` globals) resolution of
  this session's `(pid, token, kind)` via the existing
  `get_session_anchor_pid` / `get_pid_starttime` / `get_pid_starttime_kind`.
  Memoized because the tmux rung shells out and the value is invariant for the
  life of a short-lived script.
- `lock_anchor_is_self <pid> <token> <kind>` → exit 0 when all three match this
  session's anchor and our own pid is numeric; 1 otherwise. A `-`/non-numeric
  self anchor can never claim identity.

Comment the *why*: matching all three is what makes a recycled PID (same number,
different token) not read as self.

### 2. `.aitask-scripts/aitask_lock.sh` — the gate

Inside `lock_task()`'s `if [[ "$locked_by" == "$email" ]]` branch, after the
existing cross-host `LOCK_RECLAIM` emission and **before** the `PRIOR_LOCK`
line and the tree rebuild:

```bash
# Same-host, same-email: the mutex's blind spot. Refuse anything that is not
# provably THIS session or provably gone. `unknown` refuses too — see
# lib/pid_anchor.sh for why it is not rounded up to either verdict, and why
# refusing (rather than signalling after the fact) is what makes headless
# callers safe.
if [[ -n "$locked_hostname" && "$locked_hostname" != "unknown" \
      && "$locked_hostname" == "$current_hostname" ]] \
   && ! lock_anchor_is_self "$prior_pid" "$prior_starttime" "$prior_starttime_kind"; then
    case "$(lock_holder_liveness "$prior_pid" "$prior_starttime" "$prior_starttime_kind")" in
        alive)
            echo "LOCK_LIVE_HOLDER:${locked_by}|${locked_at}|${locked_hostname}|${prior_pid}"
            die_code 13 "Task t$task_id is held by a live session of yours on this host (pid $prior_pid, since $locked_at). Let it finish, or release it with './ait lock --unlock $task_id'."
            ;;
        unknown)
            # Only when an anchor was actually recorded. A lock with no anchor
            # ("-", "0", absent) has nothing to verify and keeps its legacy
            # behaviour, or every pre-anchor and non-tmux claim would refuse.
            if [[ "$prior_pid" =~ ^[0-9]+$ ]] && (( prior_pid > 0 )); then
                echo "LOCK_UNVERIFIABLE_HOLDER:${locked_by}|${locked_at}|${locked_hostname}|${prior_pid}"
                die_code 14 "Task t$task_id is held by a session on this host (pid $prior_pid, since $locked_at) whose liveness could not be established. Verify it is gone, then re-claim with --force, or release it with './ait lock --unlock $task_id'."
            fi
            ;;
    esac
fi
```

`die_code` exits immediately, so the retry loop is not re-entered. Add exit
codes 13 and 14 to the header comment block and to `show_help`'s command table.

### 3. `.aitask-scripts/aitask_pick_own.sh` — plumbing

- Header comment: document
  `LOCK_LIVE_HOLDER:<owner>|<locked_at>|<hostname>|<pid>` and
  `LOCK_UNVERIFIABLE_HOLDER:<owner>|<locked_at>|<hostname>|<pid>` (exit 1).
- `acquire_lock()`: add `13)` and `14)` to the exit-code `case` — forward the
  corresponding line and `return 4` / `return 5`.
- `main()`: route `lock_result` 4 and 5 to `force_acquire_lock` when `--force`
  is set (the force path unlocks first, so the re-lock sees no prior lock and
  the gate cannot re-fire), otherwise `exit 1`. Extend the existing
  `[[ $lock_result -eq 1 && "$FORCE" == true ]]` condition rather than adding
  parallel branches.
- **Suppress the post-claim reclaim signal after a same-email forced
  takeover.** Set a `FORCED_TAKEOVER` flag when `force_acquire_lock` succeeds
  and skip the `RECLAIM_*` block in that case. Newly needed: before this change
  a same-email lock never required `--force`, so a user who has *just*
  confirmed a force-claim would otherwise be immediately re-asked "Reclaim and
  continue?" by the crash-recovery prompt. Different-email forces are unaffected
  (they never matched `prev_assigned == EMAIL`), so `tests/test_lock_force.sh`
  is untouched.
- The existing `RECLAIM_CRASH` / `RECLAIM_STATUS` split at lines 428-445 stays
  as-is: `alive` and recorded-but-`unknown` can no longer reach it. Replace the
  stale t1466 "do not split it here" comment with a pointer to the acquire gate.

### 4. Skill surfaces (Claude Code first, per CLAUDE.md)

- `.claude/skills/task-workflow/SKILL.md` **Step 4**: add two outcomes next to
  `LOCK_FAILED:`, each with its own `AskUserQuestion`. **"Pick a different
  task" is listed first in both** — the AC requires a confirmation path whose
  default is not to take the lock:
  - `LOCK_LIVE_HOLDER:` — "a live session of yours on this host holds t\<N\>
    (pid …, since …)". Second option: "Force-claim anyway — the other session
    keeps running and both will duplicate work".
  - `LOCK_UNVERIFIABLE_HOLDER:` — "…could not be verified as running or gone".
    Second option: "Reclaim anyway (holder could not be verified)".
  Both force branches re-run `aitask_pick_own.sh <n> --force --email <e>` and
  re-parse.
- `.claude/skills/task-workflow/crash-recovery.md`: **no new signal** — the
  procedure is unchanged apart from its `RECLAIM_STATUS` description, which
  must drop "the anchored process is **alive**" and "the process cannot be
  inspected" (both are now refused at acquire and never reach this prompt).
- `.claude/skills/aitask-pickrem/SKILL.md.j2`: add both outcomes to the Step-5
  parse list → display and **abort**. Remote mode never force-claims past a
  live or unverifiable session; `force_unlock_stale` covers stale *other-user*
  locks and must not be reused here. (Belt-and-braces: the refusal already
  aborts by exit status, but an explicit arm keeps it from being reported as
  "the script failed entirely".)
- Re-render **once per profile** — `aitask_skill_rerender.sh` reads only its
  first argument, so a single call with three positional args would silently
  leave `fast` and `remote` closures stale:
  ```bash
  for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done
  ./.aitask-scripts/aitask_skill_verify.sh
  ```
  Confirm the rendered `task-workflow-{default,fast,remote}-/SKILL.md` and
  `aitask-pickrem-*/SKILL.md` actually contain the new strings before
  committing — the verifier checks structure, not freshness. Stage the rendered
  paths explicitly; the sweep touches every rendered skill dir.
- Codex (`.agents/skills/`) and OpenCode (`.opencode/skills/`) carry their own
  authoring copies of `task-workflow/SKILL.md`, `crash-recovery.md` and
  `aitask-pickrem/SKILL.md`. Per CLAUDE.md these are a **separate follow-up
  task** (the spawned "after" mitigation below), not this change.

### 5. Tests

New `tests/test_lock_live_holder_gate.sh`, built on the paired-repo fixture and
the documented `AIT_AGENT_PID` seam (copy the `setup_paired_repos` /
`plant_lock` / `run_claim` helpers from `tests/test_crash_recovery_pid_anchor.sh`):

1. **The AC test** — session A claims with `AIT_AGENT_PID=$P1` (`sleep 300`);
   session B claims with `AIT_AGENT_PID=$P2` while `$P1` still lives. Assert
   exit 1, `LOCK_LIVE_HOLDER:` present, `OWNED:` **absent**, the lock YAML still
   names `$P1`, and the task file is still unchanged (status not rewritten).
2. **Positive control** — kill `$P1`, reap, re-run B: `OWNED:` +
   `RECLAIM_CRASH:`. Proves the refusal is the gate, not a broken fixture.
3. **Self-refresh** — B re-claims with `AIT_AGENT_PID=$P2`: `OWNED:`, no
   refusal line.
4. **`--force`** — with a live holder, `--force` yields `FORCE_UNLOCKED:` +
   `OWNED:`, and **no** `RECLAIM_*` line (the suppression above).
5. **Cross-host** — same live anchor, `TEST_HOSTNAME=pc-B`: `LOCK_RECLAIM:` +
   `OWNED:`, no refusal.
6. **Unverifiable is its own outcome** — plant a live `$P1` with
   `pid_starttime: -` (and, Linux-only, a matching-token `kind: ps` variant):
   exit 1, `LOCK_UNVERIFIABLE_HOLDER:`, and neither `LOCK_LIVE_HOLDER` nor
   `OWNED`.
7. **No-anchor locks still acquire** — `pid: -` and `pid: 0`: `OWNED:` +
   `RECLAIM_STATUS:`, no refusal. Pins the split that keeps legacy and
   non-tmux claims working.
8. Syntax checks for the three touched scripts.

Retarget in `tests/test_crash_recovery_pid_anchor.sh` — both are signal
assertions the file's own comments anticipate t1466 changing ("leaves t1466 a
clean discriminator to build its acquire gate on"); their real invariant
(*not reported as a crash*) is preserved and re-asserted alongside the new
outcome:

- **Test 14** (live PID, no token) `OWNED` + `RECLAIM_STATUS` → exit 1 +
  `LOCK_UNVERIFIABLE_HOLDER`, still `assert_not_contains RECLAIM_CRASH`.
- **Test 17** `kind=ps` half → same retarget; the `kind=proc` half is self
  (same `AIT_AGENT_PID`) and stays `OWNED` + `RECLAIM_STATUS`.

Everything else stays green by construction: Tests 2/3/5/10/12 are `dead` or
no-anchor paths; Test 9 is a self re-pick; `test_lock_reclaim.sh` Test 2 is a
same-shell (self) re-lock; `test_lock_force.sh` is entirely different-email.

### Pre-phase (risk mitigations)

1. `[baseline_lock_suites]` Before editing anything, run the four affected
   suites unchanged and record their pass/fail counts:
   `tests/test_task_lock.sh`, `tests/test_lock_reclaim.sh`,
   `tests/test_lock_force.sh`, `tests/test_crash_recovery_pid_anchor.sh`.
   A pre-existing failure must be known before the diff exists, or it will be
   attributed to this change.

### Post-phase (risk mitigations)

1. `[negctrl_live_holder_gate]` With the new tests written and green, revert
   **only** the `lock_task()` gate hunk (§2), re-run
   `tests/test_lock_live_holder_gate.sh`, and confirm the named AC test (#1)
   **and** the unverifiable test (#6) **fail**. A passing negative control means
   the test is not testing the gate. Restore the hunk and re-run to green.

### 6. Documentation

- `website/content/docs/concepts/locks.md` — the "What it is" paragraph
  currently claims a competing `/aitask-pick` fails with `LOCK_FAILED`, which is
  only true for a *different* email. Replace with the exclusion guarantee the
  lock actually provides: different owner → refused; same owner, same host,
  holder alive or undecidable → refused (force required); same owner, holder
  provably gone or never anchored → reclaimable. State plainly that "same user,
  one agent" is not this project's normal mode.
- `website/content/docs/workflows/crash-recovery.md` — the three-state table's
  `alive` row becomes "acquisition refused"; the "Lock anomaly fallback"
  section loses its "the anchored process is **alive**" and "cannot be
  inspected" bullets (those no longer land there) and gains a short subsection
  for the two refusals; add a tip covering the board's manual-lock interaction
  (a lock taken from the board TUI is anchored to the board's own pane, so it
  reads as a live holder until unlocked there).
- `website/content/docs/commands/lock.md` — exit codes 13 and 14 in the command
  table.

## Verification

```bash
bash tests/test_lock_live_holder_gate.sh          # new
bash tests/test_crash_recovery_pid_anchor.sh      # retargeted 14 / 17-ps
bash tests/test_lock_reclaim.sh
bash tests/test_lock_force.sh
bash tests/test_task_lock.sh
shellcheck .aitask-scripts/aitask_lock.sh .aitask-scripts/aitask_pick_own.sh \
           .aitask-scripts/lib/pid_anchor.sh
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done
./.aitask-scripts/aitask_skill_verify.sh
grep -l LOCK_LIVE_HOLDER .claude/skills/task-workflow-*-/SKILL.md   # 3 hits
cd website && hugo build --gc --minify
```

Live end-to-end (the reported scenario, two real panes): claim a scratch task
from pane A, then run the same claim from pane B — B must refuse with
`LOCK_LIVE_HOLDER:` and leave the task file untouched; `./ait lock --list` must
still show pane A's claim.

## Risk

### Code-health risk: medium

- The gate sits on the lock critical path shared by every pick, the Step 7
  ownership guard, and the board's Lock button; a wrong self-identity comparison
  would refuse every legitimate refresh and break picking outright ·
  severity: high · → mitigation: inline pre-phase baseline_lock_suites
- Refusing on `unknown` widens the refusal surface beyond the reported defect:
  a hidepid-style procfs, or any host where the anchor cannot be inspected,
  now needs an explicit force to resume · severity: medium · → mitigation:
  inline post-phase negctrl_live_holder_gate
- Two new exit codes and two new structured outcomes must be handled at every
  consumer; blast radius spans three shell files, three skill trees plus
  rendered variants, and three website pages, and a partial sweep leaves the
  documented contract untrue · severity: medium · → mitigation: t<id> (spawned
  port_live_holder_gate_other_agents)

### Goal-achievement risk: low

- The AC maps 1:1 onto the planned changes and the discriminator already exists
  (t1465); refusing before acquisition satisfies the "must not default to
  silently taking the lock" requirement on every caller, interactive or
  headless, without per-caller parsing · severity: low · → mitigation: None
- The one path that still acquires under an undecidable holder is the
  *no-anchor* lock (`pid: -` / `0` / absent). That is deliberate — it is the
  legacy and non-tmux shape, and refusing it would bar resume outright — but it
  means the guarantee is conditional on an anchor having been recorded, and
  must be stated in the docs rather than implied away · severity: medium ·
  → mitigation: inline post-phase negctrl_live_holder_gate

### Planned mitigations
- timing: pre-phase | name: baseline_lock_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "wrong self-identity breaks picking" | desc: Record the pass/fail baseline of the four lock/anchor suites before any edit, so a retargeted assertion is distinguishable from a regression.
- timing: post-phase | name: negctrl_live_holder_gate | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "wider refusal surface" + goal "no-anchor locks still acquire" | desc: Revert only the gate hunk and prove both the live-holder and unverifiable tests fail, then restore and re-run to green.
- timing: after | name: port_live_holder_gate_other_agents | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: code-health "partial sweep across skill trees" | desc: Port the LOCK_LIVE_HOLDER / LOCK_UNVERIFIABLE_HOLDER handling from the Claude Code skills to the Codex (.agents/skills/) and OpenCode (.opencode/skills/) task-workflow and aitask-pickrem surfaces. | created: dropped(premise-false)

**`port_live_holder_gate_other_agents` was dropped at Step 8d — its premise was
false.** The design assumed Codex and OpenCode carry their own authoring copies
of `task-workflow` and `aitask-pickrem`. They do not: `ls -d
.agents/skills/*/ .opencode/skills/*/` shows no `task-workflow` authoring dir at
all, and the `aitask-pickrem` entries in both trees are 27-line dispatch stubs,
not content. Every agent renders from the single Claude authoring source
(`.claude/skills/task-workflow/` and `.claude/skills/aitask-pickrem/SKILL.md.j2`),
so `aitask_skill_rerender.sh` already propagated this change to all three trees.
Verified by sweeping every rendered closure in `.claude/`, `.agents/` and
`.opencode/` for the new strings: the only miss was a git-ignored `_skillrun_`
scratch dir. Creating the task would have created an empty one.

The mistaken premise came from my own exploration, not the repo: an earlier
`grep -rln … | sed 's/-[a-z]*-\(codex-\)\?\//\//'` rewrote rendered paths like
`task-workflow-fast-codex-/` into `task-workflow/`, manufacturing authoring
paths that do not exist. A path-normalizing filter over a file listing can
invent files — check existence before concluding one is stale.

## Final Implementation Notes

- **Actual work done:** Implemented as planned. `lib/pid_anchor.sh` gained
  `lock_anchor_is_self()` over a memoized own-anchor triple;
  `aitask_lock.sh::lock_task()` gained the same-host/same-email acquire gate
  (exit 13 `LOCK_LIVE_HOLDER:`, exit 14 `LOCK_UNVERIFIABLE_HOLDER:`, both
  emitted and refused before the lock write, the status update and the commit);
  `aitask_pick_own.sh` forwards both, routes them to `force_acquire_lock` under
  `--force`, and suppresses the post-claim reclaim signal after a confirmed
  same-email force. Skill surfaces: two new outcomes in `task-workflow`
  Step 4 (safe option listed first in both prompts) and in the Step 7 ownership
  guard, a scope note in `crash-recovery.md`, and abort arms in
  `aitask-pickrem`'s `.j2`. Docs: an exclusion-guarantee table in
  `concepts/locks.md`, a "When the Holder Is Still Running" section plus a
  board-lock tip in `workflows/crash-recovery.md`, exit codes in
  `commands/lock.md`. Tests: new `tests/test_lock_live_holder_gate.sh`
  (60 assertions), two retargeted assertions in
  `tests/test_crash_recovery_pid_anchor.sh`, one fixture fix in
  `tests/test_lock_anchor_tmux_live.sh`.

- **Deviations from plan:**
  - *A fifth suite needed changing.* The plan baselined four suites;
    `tests/test_lock_anchor_tmux_live.sh` was not among them and broke. Its
    Case B negative control re-claimed the *same* task Case A had just locked
    from a still-live pane, so the new gate refused it before the writer ran.
    The guard is correct — a claim that cannot resolve its own anchor cannot
    prove it is the holding session — so the fixture was retargeted onto its own
    task (t2) rather than the gate being softened. The negative control is
    fully preserved: Case B still proves the writer degrades to `pid: -`.
  - *The spawned "after" mitigation was dropped*, premise verified false — see
    the note under `### Planned mitigations` above.
  - *`show_help()` was updated too* (review finding). The top-of-file contract
    block had been updated but `show_help()` still described `--force` as
    stale-lock-only and listed neither new output, so `--help` contradicted the
    code this task shipped. Two adjacent stale phrasings in the same file (the
    usage line and `FORCE_UNLOCKED`'s description, both saying "stale lock")
    were aligned at the same time.

- **Issues encountered:**
  - *Test hang.* A `start_session()` helper returning a pid via command
    substitution hung: the backgrounded `sleep` inherits the substitution's
    pipe and holds it open. Inlined as `sleep 300 >/dev/null 2>&1 & PID=$!`,
    which also keeps the process a direct child so `wait` can reap it — an
    unreaped zombie still has a `/proc` entry and answers `kill -0`, so it
    would read as ALIVE and silently invalidate every "dead" assertion.
  - *`set -e` and `[[ … ]] && return N`.* An AND-list whose test fails takes the
    list's non-zero status and kills the function before any fallback return.
    Written as an explicit `if` in `acquire_lock`'s 13/14 arm.
  - *A self-inflicted over-broad guard.* The negative-control script asserted
    the removed slice contained no `LOCK_RECLAIM`; it tripped on the *word* in
    a comment. Tightened to the emission (`echo "LOCK_RECLAIM`). The file was
    not modified — the assertion fired before the write.

- **Key decisions:**
  - *Refuse, do not acquire-then-signal.* Both new outcomes refuse before any
    write, so nothing has to be given back. This is what makes the headless lane
    safe **by construction**: `aitask-pickrem` parses no `RECLAIM_*` signal at
    all, so any design that acquires first and signals afterwards is
    automatically taken over in remote mode. A post-claim
    `RECLAIM_UNVERIFIABLE:` signal was designed and then discarded for this
    reason.
  - *Self-refresh is exempt, on all three fields.* `(pid, token, kind)` must all
    match. Matching the pid alone would call a recycled PID "self" and disable
    the gate; without the exemption the gate would refuse the Step 7 ownership
    guard, every in-pane re-pick and every in-flight resume.
  - *"Recorded but undecidable" and "never recorded" are different states.* The
    first refuses; the second (`pid: -` / `0` / absent) keeps its old behaviour.
    Refusing the second would strand every pre-anchor lock and every non-tmux
    claim. This is the stated boundary of the guarantee and is documented as
    such rather than implied away.
  - *An unresolvable own anchor never claims identity* — it fails toward the
    gate, not around it. The measured cost: a session whose tmux gateway becomes
    unreachable is refused its own lock and needs `--force`. Accepted, since the
    alternative is a hole exactly the size of the bug.

- **Upstream defects identified:** None.
