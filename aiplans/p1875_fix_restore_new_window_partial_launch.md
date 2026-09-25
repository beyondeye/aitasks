---
Task: t1875_fix_restore_new_window_partial_launch.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1875 — Gone-pane restore: never leave a launched agent window untracked

## Context

`agent_restore._launch_into_new_window` (`.aitask-scripts/lib/agent_restore.py:540`)
starts the replacement agent with `launch_in_tmux(..., new_window=True)`, then
resolves its pane with `resolve_pane_id_by_pid`. Three partial-success shapes
leave an agent window running that no record tracks, while `_rollback` puts the
record back to `frozen` as though nothing had launched:

1. `new-window` succeeded but `-P` did not parse → `(None, None)`;
2. the gateway folds a timeout into rc `-1` after the server created the window;
3. `resolve_pane_id_by_pid` misses the pid.

A fourth instance of the same class sits in `restore()` itself. In the
new-window branch the local `pane_id` stays `""`, so every later rollback
(`launch_refused`, and `_settle` on `session_mismatch`) calls
`_rollback(..., pane_id="")`. The same-pane branch kills its agent there; the
new-window branch leaves the resumed agent running untracked.

Two gaps make any survivor dangerous, whatever caused it. **Both were verified
in the code:**

- **Retry duplicates.** `restore()`'s preflight probes only the record's
  `pane_id` (`agent_restore.py:634`). A survivor that the record does not name is
  invisible to it, so the next restore launches a second agent on the same session.
- **Reopen adopts an agent as a viewer.** `agent_reopen._claimed_panes` claims any
  pane stamped `@aitask_frozen=<id>`. `_adopt` then commits `standin-respawned`
  **without respawning** (`agent_reopen.py:509-559`), so a stamped pane that still
  runs the restored agent becomes the record's "viewer": the record says `frozen`
  while the agent is live. A later restore then `respawn-pane -k`s it as though it
  were a stand-in. Reconcile's crash path reaches that end state too:
  `_reconcile_restoring` with `observed is None` aborts to a gone-pane `frozen`
  (`agent_freeze.py:1214`).
- **A reused pane id hides a survivor.** The stored `pane_id` is only a hint, and
  pane ids restart at `%0` after a server restart. A survivor that happens to get
  R's recorded `%N`, stamped `@aitask_frozen=R`, passes the preflight probe as R's
  own stand-in, and the same-pane branch then `respawn-pane -k`s the running
  agent. Reopen, likewise, calls it `tracked`.

## Design

### A durable attempt identity, on the pane, from the first instant

- **Creation.** The window is created with `new-window` through the gateway
  (`frozen_ops.run`) under the attempt name
  `aitask-restore-<record_id>-<nonce[:8]>`. tmux sets the name atomically, so the
  window is never unclaimed. Request `-P -F "#{pane_id}\t#{pane_pid}"`, so the
  pane id comes from tmux directly (this removes shape 3 and
  `resolve_pane_id_by_pid`). Keep the current shape: no `-d`, `-c root`, and the
  bare `_env_prefixed` command (the t1465 pane-pid contract).
- **Durable mark.** Once the pane is identified, one name-guarded
  `if-shell -F "#{==:#{window_name},<attempt>}"` dispatch sets
  `@aitask_frozen=<id>`. A second name-guarded dispatch sets the new option
  `@aitask_restore_attempt=<id>:<nonce8>`. Both are verified by a re-read. The
  stamp is what lets the existing `_rollback` put the stand-in back into this
  window. The attempt option is what makes the window identifiable as **a
  restore-launched agent** after the rename.
- **Rename (early).** Then comes a stamp-guarded rename to the final
  `agent-…` name, because the monitor (`monitor_app.py:3502`) and the companion
  spawn (`agent_launch_utils.py:2146`) key on the `agent-` prefix. A failed rename
  is non-fatal: the code prints a `WARNING:` and the window keeps the attempt name.
- **The invariant both coordinators rely on: survivor identity is decided from the
  pane's own evidence, never from R's `pane_id`.** The stored `pane_id` is only a
  hint. After a server restart pane ids start again at `%0`, so a survivor can get
  exactly the id R recorded. The rule is therefore:

  > A live pane that claims R through a restore attempt (the attempt mark, or an
  > `aitask-restore-<R>-…` window name) is a **survivor** unless it proves it is
  > R's viewer by carrying `@aitask_standin_ready == R`.

  That proof is sound for three reasons. Only a mounted stand-in sets the ready
  mark (`frozenagent_app.py:328`). Every respawn *into an agent* clears it in the
  same `if-shell` dispatch (`unset=STANDIN_READY_OPTION`, forward restore). And a
  freshly created window never carries it. There is **no own-pane exclusion**, and
  `tracked` does not take precedence over this rule. A survivor at R's recorded
  `%N` is still a survivor.

  The predicate `restore_attempt_record(window_name, option_value) -> record_id | ""`
  and the constants live in `agent_frozen_ops.py`, the shared module both
  coordinators already import. (`monitor_core.py` is being edited by a concurrent
  session, so it is not touched.)

### Identification and cleanup inside `_launch_into_new_window`

- `-P` did not parse, or rc != 0 → look the window up by its attempt name with
  `list-panes -s -t =<session>:`:
  - `found` → carry on with that pane (the window is recorded, not rolled back);
  - `none` → `launch:rc=<rc>` (truthful: tmux holds no window for the attempt);
  - `unknown` → `launch_uncertain:<attempt>`. Any window that does exist is still
    identifiable by its name, so the survivor guard below catches it on the next
    run.
- The stamp or the attempt option does not verify → name-guarded kill
  (`if-shell` on the attempt name, `kill-window`, then an after-read). The error is
  `stamp`, plus `|cleanup:<verdict>:<reason>|pane:<id>` whenever the kill was not
  verified `gone`.
- Once the pane is identified the helper returns it, so that `restore()` sets
  `pane_id = new_pane`. From then on rollback (stand-in into the new window),
  `_settle`, liveness `pane_location`, and the stamp clearing all address it.

### Settlement clears the attempt mark

- **Success** (hook or liveness): `_clear_frozen_stamp` also unsets
  `@aitask_restore_attempt`.
- **Rollback: the mark is removed only after the replacement is verified.**
  `respawn_if_stamped` runs every `unset` *ahead of* `respawn-pane -k` in its
  branch. If the attempt mark were one of those unsets, a failed respawn would
  strip the mark from a pane that still runs the agent. The early rename has
  already removed the attempt name, and `_rollback` would then commit a
  gone-pane `frozen`, leaving no claim for any guard to see. So the attempt mark
  is **never** part of the pre-respawn `unset`. `respawn_if_stamped` is not
  changed; its single `unset=STANDIN_READY_OPTION` stays as it is. `_rollback`
  calls `frozen_ops.unset_option(new_pane, RESTORE_ATTEMPT_OPTION)` **only when
  `fired` is True**: the branch token is the positive proof that the stand-in
  replaced the agent. On every miss (`respawn-failed`, `stamp-mismatch`,
  `server-restarted`, `pane-gone`) the mark is left untouched, so the pane stays an
  identified survivor.
- **Every mark removal is guarded by the exact attempt value.** A bare
  `unset_option` is a separate tmux call. A server restart between a verified
  respawn and that call can hand the same `%N` to **another record's** restore
  attempt, and an unguarded unset would erase that agent's only claim. Its early
  rename already removed the attempt name. So the removal is one dispatch:
  `if-shell -F -t <pane> "#{==:#{@aitask_restore_attempt},<R>:<nonce8>}"
  "set-option -pu -t <pane> @aitask_restore_attempt"`. The value names both the
  record and the attempt nonce, so it matches only the pane this attempt created.
  In any other pane the branch declines and touches nothing. The helper
  `frozen_ops.clear_restore_attempt(pane_id, value)` is used by `_rollback`
  (after `fired`) and by the success path.
- **The success path's stamp clear is guarded the same way.** `_clear_frozen_stamp`
  today unsets `@aitask_frozen` unguarded, which has the same recycled-id shape:
  it could strip another record's stamp. It becomes
  `if-shell "#{==:#{@aitask_frozen},<R>}" "set-option -pu …"`. It clears the
  attempt mark only when the caller knows the value, so it takes an optional
  `attempt` argument; the new-window branch passes it.
- Reconcile (`agent_freeze.py`, not changed here, and dirty in a concurrent
  session) can settle a crashed attempt without knowing about the mark:
  `restore-confirm` or `_respawn_standin`. Its stand-in respawn fires only after
  the stamp guard. A pane it confirms `live` is not a `frozen` record's concern.
  If that record is later frozen again, its stand-in mounts and sets the ready
  mark.
- A stale mark left behind (for example, an unset that failed after a success) is
  resolved by the ready-mark proof: once a stand-in mounts in that pane, it proves
  it is a viewer. Until then the pane blocks, which is the fail-safe direction.

### Concern 1 — the retry guard (`restore()` preflight, every branch)

Before `restore-begin`, **and before the recorded-pane probe chooses the
same-pane branch**, a single `list-panes -a` pass reads pane id, dead flag,
session, window name, `@aitask_restore_attempt` and `@aitask_standin_ready`. It
applies the survivor rule to every pane, R's recorded `%N` included. A survivor
sitting at R's own `pane_id` is refused here. It is never `respawn-pane -k`'d as
though it were R's stand-in.

- rc != 0 → `RESTORE_FAILED:<id>|preflight:tmux unreachable` (fail closed);
- a live survivor of R → `RESTORE_FAILED:<id>|restore_survivor:<session>:<window>|pane:<p>`.
  No lease is taken and nothing is launched. The only guidance given is: *that
  window runs an agent from an earlier restore that the record does not track.
  Close it to retry the restore.* There is **no** "drop the record to keep it"
  advice. The framework has no safe action that keeps that agent and retires the
  record, and `drop` refuses survivors (below);
- a dead survivor → guarded kill (on the mark or the name). It is ignored only if
  the kill is verified `gone`; otherwise it blocks like a live survivor.

### Concern 2 — reopen distinguishes an agent from a viewer before committing

- `_claimed_panes` reads the attempt option as one extra claim field. A pane whose
  mark or attempt name names R gets a claim `via="restore"`, in addition to any
  stamp claim. The claim already carries `ready`.
- `classify_record` **checks for a survivor first**: any live `restore` claim whose
  `ready != R` → the new kind **`survivor`**, ahead of both `tracked` and
  `stranded`. This includes a claim on R's own `pane_id`. A survivor is never
  adopted, never duplicated, and never reported `pane_present`. `reopen_one` returns
  `REOPEN_FAILED:<id>|restore_survivor:<session>:<window>|pane:<p>` before taking
  a lease.
- `gone_line` emits kind `survivor`. `ide_frozen_offer.sh` marks it
  `(an earlier restore's agent is still running, untracked)`, and
  `_ide_frozen_restore` skips it with a message, the same shape it uses for
  `stranded`.

### Drop refuses a restore survivor

`agent_freeze.drop_record` resolves its target from the record's `pane_id`. If
the pane is present and stamped `@aitask_frozen == R`, it `kill_if_stamped`s it
(`agent_freeze.py:1395-1410`). Two survivor shapes defeat that:

- **equal id**: the survivor *is* the recorded `%N`, so drop kills a running agent;
- **different pane**: the ordinary crash or uncertain-launch state (m5/m6). R's
  `pane_id` is empty or names a gone pane, drop kills nothing, and it then
  **deletes R and its capture while the survivor keeps running**. That recreates
  an untracked agent with no record left at all.

A per-pane check only catches the first shape. So drop runs the **same
whole-server scan** as the restore preflight: `frozen_ops.find_restore_survivors(record_id)`
(below). It runs right after `lease-take` and **before** the target resolution,
any kill, and the `drop` store verb:

- the scan cannot read tmux → release the lease and return
  `DROP_FAILED:<id>|preflight:tmux unreachable` (fail closed);
- any live survivor of R, in any pane, R's recorded `%N` included → release the
  lease and return `DROP_REFUSED:<id>|restore_survivor:<session>:<window>|pane:<p>`.
  There is no kill, and the record and its capture are untouched.

**No scan-to-delete race exists here.** Drop holds R's lease for the whole
sequence. A survivor of R can only be created by a restore attempt of R, which
needs that lease, and a server restart destroys every pane that existed before
it. So between the scan and the store deletion, no survivor of R can appear in
any pane. A recycled `%N` stamped with another record's id is still declined
by `kill_if_stamped`'s own stamp check. This reasoning is written as a comment
at the check.

Consumers need no change. The CLI prints the `DROP_REFUSED:` line verbatim and
exits 1 (`aitask_frozen.sh`). The frozenagent TUI's detached drop observes only
the record's continued existence (`agent_sessions.drop_verdict`), so it reports
"drop failed — record kept". That is true, and it is the fail-safe message.

## Implementation steps

1. `agent_frozen_ops.py`: `RESTORE_ATTEMPT_OPTION = "@aitask_restore_attempt"`,
   `RESTORE_ATTEMPT_RE = ^aitask-restore-([0-9a-f]{8})-([0-9a-f]{8})$`,
   `restore_attempt_name(record_id, nonce)`,
   `restore_attempt_record(window_name, option_value)`, and
   `is_restore_survivor(record_id, window_name, option_value, ready, dead)`. The
   last one is the single rule both coordinators call. Also add
   `find_restore_survivors(record_id) -> list[Survivor] | None`: one `list-panes -a`
   pass that returns pane id, pid, session, window, dead, mark and ready, with
   `None` when tmux is unreachable. Restore's preflight and drop both call it;
   reopen applies the same predicate to its own claim listing;
   `clear_restore_attempt(pane_id, value)` (guarded by the exact value in one
   `if-shell` dispatch), and `clear_stamp_if(pane_id, record_id)` (guarded by the
   stamp). `respawn_if_stamped` is **not** changed.
2. `agent_restore.py`:
   - add a `_seam(stage)` helper (comma-set semantics on `AITASKS_RESTORE_FAIL_AT`,
     with no collision with begin/respawn/ack). The stages are `launch_uncertain`,
     `identify`, `lookup`, `stamp`, `cleanup`, and `abandon`. `abandon` returns an
     error after the marks and the rename, doing no cleanup: it reproduces the end
     state of a coordinator crash;
   - add local helpers `_find_attempt_pane`, `_kill_if_named`, and
     `_rename_if_stamped`, cross-referenced to reopen's twins. They cannot be
     imported, because `agent_reopen` imports `agent_restore`;
   - add the preflight guard in `restore()` over
     `frozen_ops.find_restore_survivors(record_id)` (no own-pane parameter, by
     design), placing it placed **before** the recorded-pane probe
     and before `restore-begin`;
   - rewrite `_launch_into_new_window` (the return contract is unchanged). In
     `restore()`, set `pane_id = new_pane` after it; unset the attempt option in
     `_clear_frozen_stamp`, which becomes guarded (`clear_stamp_if`, plus
     `clear_restore_attempt` when the attempt value is known). `_rollback` keeps
     its single `unset=STANDIN_READY_OPTION`. After the dispatch, and only when it
     `fired`, it calls `clear_restore_attempt(new_pane, <R>:<nonce8>)`;
   - drop imports that are now unused, verified with grep;
   - docstring: a "partial launch and survivors" paragraph and the new seams.
3. `agent_reopen.py`: extend the claim format to 8 fields and add the `restore`
   claim. Add the `survivor` kind: `classify_record` checks for it **before**
   `tracked`, and `reopen_one` / `reopen_all` handle it; update the module docstring's CLASSIFICATION section.
4. `ide_frozen_offer.sh`: the survivor marker and the skip in
   `_ide_frozen_restore`.
4b. `agent_freeze.py` `drop_record`: call `find_restore_survivors` right after
   the claim and before target resolution, as described in "Drop refuses a
   restore survivor". Add the lease comment, and add step "0b. survivor scan" to
   the docstring's ordered list.
5. `website/content/docs/workflows/freeze-and-restore-agents.md`: next to the
   `viewer open, untracked` paragraph, one sentence on the survivor marker. It
   says: this is an agent from an earlier restore that is still running and
   untracked; restore, re-pick and drop refuse the record; close that window to
   retry. It gives no advice to drop in order to keep the agent. Current-state prose only. Then run
   `python3 website/check_links.py --build`.
6. Unit tests:
   - `tests/test_agent_restore.py`: replace the `launch_in_tmux` /
     `resolve_pane_id_by_pid` patches in the two new-window classes with a
     window-aware fake tmux (modelled on `test_agent_reopen.py`'s). Add
     `TestNewWindowPartialLaunch`: unparsed or rc -1 + found → recorded;
     rc -1 + none → `launch:rc=-1`; unknown → `launch_uncertain:<name>`; a stamp
     that does not verify → name-guarded kill, and a kill left `present` is named;
     a failed rename is non-fatal. Add `TestRestoreSurvivorGuard`:
     - a live survivor blocks before `restore-begin`, so no store call is made;
     - a dead survivor is killed and does not block;
     - **equal-id survivor**: the record's `pane_id` is `%5`, and `%5` carries
       `@aitask_frozen=R` plus the attempt mark with no ready mark. The result is
       `restore_survivor`, and no `respawn-pane` or `if-shell` respawn is
       dispatched. This is red against the current code, which respawns over it;
     - a marked pane that carries `@aitask_standin_ready=R` (a settled viewer)
       does not block, and goes through the same-pane branch;
     - **a respawn that fails after the option removals**: in the fake tmux, the
       `if-shell` branch runs its `set-option -pu` but `respawn-pane` fails, so
       there is no token. After `_rollback`, the pane still carries
       `@aitask_restore_attempt` and the stamp, and the record is committed
       gone-pane. A following `restore()` is then refused with `restore_survivor`,
       and no `new-window` is dispatched. Also check that the dispatched branch
       text never contains the attempt option;
     - the rollback respawn fires (token seen) → the attempt mark is cleared by a
       dispatch guarded on the exact value, issued only after the respawn dispatch;
     - **recycled-id cleanup race**: the rollback fires, and then, before the
       clear, the fake tmux replaces the pane at that `%N` with one carrying
       `@aitask_restore_attempt=<R2>:<other>` and `@aitask_frozen=<R2>`. After
       `_rollback`, the stranger's mark and stamp are both intact. The same check
       runs for the success path's `_clear_frozen_stamp`. Both are red against a
       bare `unset_option`. The
     `restore()` new-window + `session_mismatch` case → `_rollback` receives the
     NEW pane (red against the current code).
   - `tests/test_agent_reopen.py`: a stamped pane that carries the attempt mark →
     `survivor`, not `stranded`, and no `standin-respawned` is written. This is
     red against the current reopen code, which adopts it. A name-only attempt
     window → `survivor`. **Equal id:** a survivor on R's recorded `pane_id` →
     `survivor`, not `tracked` or `pane_present`. R's own pane with a stale mark
     **and** `ready == R` → `tracked`.
   - `tests/test_agent_freeze.py`, `drop_record` against survivors. Each case is
     red against the current drop:
     - **different-pane survivor** (the m6 shape): the record's `pane_id` is empty
       or a gone `%N`, and another pane carries R's attempt mark with no ready
       mark. Expect `DROP_REFUSED:<id>|restore_survivor:…|pane:<p>`, no `drop`
       store verb (the record and capture are kept), no kill, and the lease
       released. The current drop deletes the record here;
     - **name-only survivor**: an unmarked `aitask-restore-<R>-…` window → the
       same refusal;
     - **equal-id survivor**: the record's `pane_id` is the survivor → the same
       refusal, and no `kill-window` or `kill-pane` (the current drop kills it);
     - a marked pane with `ready == R` is still dropped (a viewer); another
       record's survivor does not block R; an unreadable scan →
       `DROP_FAILED …|preflight:tmux unreachable` with nothing deleted.
   - `tests/test_agent_frozen_ops.py`: cover `is_restore_survivor`'s truth table:
     a mark or name for R with no ready mark → survivor; `ready == R` → not a
     survivor; a dead pane → not a live survivor; another record's mark → not R's
     survivor.
7. `tests/test_frozen_reopen_live.sh`: section `m`, "a gone-pane restore never
   leaves its agent untracked":
   - m1 mismatch (`tm set-environment -g FAKE_AGENT_SESSION sess-wrong`) →
     `RESTORE_FAILED`; the record is `frozen` on the new window's pane; the
     stand-in is back in it (stamp, and no attempt mark); exactly one window.
     This is red against the current code;
   - m2 `identify`, and m3 `launch_uncertain` → restored through the name lookup:
     `live`, final `agent-…` name, no attempt mark, one window;
   - m4 `identify,stamp` → `stamp` failure, and no window survives;
   - m5 `identify,lookup` → `launch_uncertain:aitask-restore-<id>-…`. A **retry**
     is refused with `restore_survivor` and creates no second window; `gone` lists
     the record as `survivor`, and `reopen` refuses it without creating a viewer.
     After the test closes that window, the retry restores;
   - m6 `abandon` (the crash end state: a stamped, marked, renamed survivor, and
     the record `frozen` on a gone pane) → `reopen` does **not** adopt it (the
     record still names no pane, and the pane still runs the agent); `restore` is
     refused with `restore_survivor`; `ait ide`'s R skips it with the marker;
     **`drop` is refused with `restore_survivor`**, and the record, its capture
     and the survivor's pid are all unchanged;
   - m7 **equal-id survivor**: from m6's state, `lease-take` then
     `standin-respawned --pane <survivor> --pane-pid <its pid>`. This makes the
     record name the survivor's `%N`, the same state a pane-id reuse after a
     server restart produces. `restore` → `restore_survivor`, and the survivor's
     `#{pane_pid}` is unchanged (it was not respawned). `reopen` → reports
     `restore_survivor`, never `REOPEN_SKIPPED …|pane_present`. `drop` →
     `DROP_REFUSED:<id>|restore_survivor`; the survivor pane is still alive with
     the same pid, and the record and its capture still exist. Afterwards the test
     closes the window, and `drop` then succeeds;
   - update the header's case list.

### Post-phase (risk mitigations)

1. [run_frozen_live_regressions] Run the other live suites that drive real
   restores and rollbacks, and require each one to end with its all-pass line:
   `bash tests/test_restore_flows_live.sh`,
   `bash tests/test_restore_session_bootstrap_live.sh`,
   `bash tests/test_frozen_agents_acceptance.sh`,
   `bash tests/test_frozen_respawn_atomic_live.sh`,
   `bash tests/test_ide_frozen_offer.sh`, `bash tests/test_freeze_engine_live.sh`
   (drop changed). Fix in this task, before the commit, any failure that touches
   the gone-pane branch, the survivor guard, or drop.

## Verification

- `python3 -m pytest tests/test_agent_restore.py tests/test_agent_reopen.py tests/test_agent_frozen_ops.py -q`
- `bash tests/test_frozen_reopen_live.sh` → `ALL TESTS PASSED`
- Red proofs (m1, the unit mismatch-rollback case, the reopen survivor unit case,
  both equal-id cases, unit and m7, the drop refusals for both the different-pane
  and the equal-id shapes, and the recycled-id cleanup race): run them against the pre-fix modules in an isolated copy, never by
  stashing or restoring the shared worktree.
- `bash tests/run_all_python_tests.sh --test-dir tests` → final line
  `PYTHON SUITE: PASSED`.
- Commit only this task's paths (concurrent session edits in the tree).
- Step 9 (Post-Implementation): archival per the workflow.

## Risk

### Code-health risk: medium
- `restore()` is a load-bearing transaction. Re-routing rollback, settle and
  liveness to the new pane, and adding a preflight scan, touches every gone-pane
  restore. A mistake could kill a successfully restored agent or block restores
  that are legitimate. The success paths are unchanged, and rollback is still
  gated by the store's state guard and the stamp guard. A settled viewer is
  exempted only by its own ready-mark proof, never by pane-id equality. A viewer
  whose stand-in has not mounted yet is blocked briefly, which is the fail-safe
  direction. · severity: medium · → mitigation: inline post-phase run_frozen_live_regressions
- The attempt mark is cleared in a second call after a verified rollback respawn,
  so it is not atomic with the respawn. If that unset fails, a settled viewer keeps
  a stale mark and blocks until its stand-in's ready mark proves it is a viewer.
  That is the fail-safe direction, and it is accepted. · severity: low · → mitigation: none (accepted)
- The helpers duplicate reopen's name-lookup, kill and rename logic. This is
  bounded and cross-referenced, a deliberate trade against a circular import. · severity: low · → mitigation: dedupe_window_name_helpers
- A new kind of classification (`survivor`) is added to the wire vocabulary.
  Every consumer, which grep shows to be `agent_reopen.py` and
  `ide_frozen_offer.sh`, is updated in this task. · severity: low · → mitigation: none (in scope)

### Goal-achievement risk: low
- Survivors are blocked and reported, not adopted automatically. A user whose
  earlier restore's agent is still running must close that window before the
  record can be restored or dropped. No action keeps the survivor and retires the
  record, and none is advertised.
  Adopting it automatically would need a liveness-only confirm against an agent
  that carries a stale nonce, which is out of scope. · severity: low · → mitigation: none (accepted)

### Planned mitigations
- timing: post-phase | name: run_frozen_live_regressions | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — rollback/settle/liveness re-routing | desc: run the other real-restore live suites after the change
- timing: after | name: dedupe_window_name_helpers | type: refactor | priority: low | effort: low | inline_risk: medium | added_complexity: low | addresses: code-health — duplicated window-name helpers | desc: move name lookup, name-guarded kill and stamp-guarded rename into agent_frozen_ops, shared by agent_reopen and agent_restore
