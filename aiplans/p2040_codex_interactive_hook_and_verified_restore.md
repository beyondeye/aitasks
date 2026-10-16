---
Task: t2040_codex_interactive_hook_and_verified_restore.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2040 — Codex: verified restore from the resumed process, late-hook fix, refreshed claims

## Context

Measured on codex 0.163.0, interactive codex now fires SessionStart. It fires at the
**first turn**, not at launch. A process started with `codex resume <sid>` holds its
rollout open from launch. Today every codex restore still ends `ack=liveness`
("restored, unverified — capture kept"), because no hook can arrive within the 20 s grace.
On top of that, the restored agent's hook is **refused** when it finally fires
(`TRANSITION_REFUSED`: the record is already `live`). So the pane is never re-stamped, and
every later SessionStart in that process is refused the same way.

Goal: on Linux, a codex restore is verified the way Claude's is. The hook stops being
refused. Every "codex fires no interactive hook / can only reach liveness" claim states
the version boundary instead. Older codex and platforms without `/proc` keep today's
paths.

**Scope decision (user):** the macOS `lsof`/`ps` fallback (merged from t1821) is **split
into a follow-up task**. It is not implemented here.

Current-branch mode (profile `fast`): no worktree.

## Design decisions

### D1. New evidence: the resumed process's open rollout (`ack=rollout`)

The coordinator accepts this as **verified** evidence when all of these hold: the record is
codex, the restore is in `resume` mode, and `codex_session_for_pid(launch_pid)` returns a
session id. The **store** makes the comparison, the same way it does for the hook ack:
- **match** → `live`, `ack=rollout`, captures deleted, `last_error` cleared, lease cleared;
- **mismatch** → persist `<nonce>:session_mismatch` and raise `SessionMismatch` (exit 7).
  The coordinator's normal re-read then rolls back, through the hook-mismatch channel that
  already exists.

**Why this is a deliberate change from "only the hook counts".** It goes into the
docstrings at `agent_restore.py` L15-27, `agent_sessions.py` L855-857 and
`agent_frozen_ops.py` L115-119:
- The fact is the same one the hook reports (which conversation this process is in).
  Here it comes from the kernel rather than from an env-inheriting child process.
- The pid is the one the nonce-bound `restore-launched` recorded for this attempt.
  `restore-confirm` already requires `launch_pid == observed pid`.
- `codex_session_for_pid` checks inside itself that argv0 is codex. It reads only the
  depth-0 fds, folds subagent rollouts into their parent's id, and refuses to choose
  between two sessions (`MISS_AMBIGUOUS`). So "could not prove" never becomes a verdict.
- A resume that silently started a fresh session holds a *different* id, or none. A
  different id aborts. No id falls back to liveness, as today.

Form: an **option on `restore-confirm`** (`--rollout-session <sid>`), not a new verb. It
keeps the nonce, state and `launch_pid` checks and the wrapper's `cmd_leased` dispatch.
The evidence gets its own `ack` value, so a rollout confirm is never mislabelled `hook`.

### D2. The late `source=resume` hook (task item 3): upgrade when provable, otherwise a plain upsert

In `upsert`, when `restore_of` names a record that is already **`live`**:
- **Upgrade to verified** (`ack=hook`, captures deleted, `UPSERTED:<id>|restored_late`)
  only when all of these hold:
  - `rec.ack == "liveness"`
  - `rec.launch_pid != 0` and it equals the caller's `pane_pid`
  - `rec.pane_id` equals the caller's pane
  - the session agrees: in `resume` mode it equals the stored id; in `repick` mode it is
    non-empty and is adopted.

  This replaces the nonce check, which is impossible here because `restore-confirm` cleared
  `op_nonce`. `launch_pid` is attempt-scoped (`restore-begin` zeroes it,
  `restore-launched` sets it), so it binds the ack to the process this restore launched.
- **The late window closes when the session moves (review fix).** In the ordinary update
  path, any upsert that **changes or clears** the stored `codeagent_session_id` also sets
  `launch_pid = 0`.

  Without this, the sequence `live/liveness, target A` → late hook **B** (falls through,
  adopts B) → hook **B** again would match the *mutated* stored id and delete A's
  captures, although A was never verified. Zeroing `launch_pid` makes the stored id at
  upgrade time always the restore's target, because nothing can have changed it while
  the window is open.

  `launch_pid` has no consumer on a `live` record (only `restoring`-state reconcile, the
  confirm and launched verbs, and `restore-begin`, which re-zeroes it), so this costs
  nothing elsewhere.
- **Otherwise, a plain upsert:** drop `restore_of`/`nonce` and run the ordinary selection
  (`--id` from the pane stamp, else pane identity). This is what makes `/new` and every
  later SessionStart update the record instead of being refused. A different session id
  is adopted as the pane's current conversation, as for any ordinary upsert.
- States `frozen`, `freezing` and `aborting` are **still refused** (`TransitionRefused`).
  `restoring` keeps today's nonce and mismatch path.

### D3. Two side defects (confirmed in planning)

- `restore_confirm` does not check `last_error`. A `session_mismatch` that lands between
  the last poll and `restore-confirm` is confirmed anyway. **Fix:** refuse (`TransitionRefused`)
  when `last_error` starts with `f"{nonce}:"`. This applies to liveness and rollout alike.
- **The recovery handover (review fix).** The guard above alone does not cover reconcile.
  `_reconcile_restoring` judges a mismatch from its *pre-lease* snapshot (original nonce
  N1). `lease_take` then mints N2 and keeps `last_error` as it is. So a hook mismatch
  persisted between the snapshot and `lease_take` stays `N1:session_mismatch`, and a
  confirm under N2 would ignore it. Two parts:
  - **Transfer the correlation atomically.** Inside the store lock, `lease_take` rewrites
    a `last_error` that starts with the outgoing `op_nonce` (non-empty) to the incoming
    nonce. The error belongs to the attempt, and the attempt now belongs to N2. An error
    from an older attempt (different prefix), and records with no lease (`op_nonce` empty,
    e.g. `frozen` under `drop`), are untouched. The D3 store refusal then holds after a
    takeover too.
  - **Re-check after acquiring the lease.** In reconcile's `launch_pid == observed pid`
    row, take the lease first (`nonce = lease()`), re-read with
    `frozen_ops.store_show`, and abort back to frozen (`_abort_back_to_frozen`) if
    `last_error` starts with `f"{nonce}:"`. Only then try the rollout or liveness
    confirm. After `lease_take` the hook's N1 ack is a `NonceMismatch` that writes
    nothing, so this re-read is final.
- The refused-confirm re-read (`agent_restore.py` L1000-1002) returns without `_settle`,
  so a mismatch found there never rolls back. **Fix:** `return _settle(decided, …)`.

## Implementation steps

0. **Coordinate with in-flight t2039 (same checkout).** t2039 (`Implementing`) has
   **uncommitted** hunks in three files this plan also edits:
   - `lib/agent_restore.py`: it splits `restore()` into a wrapper plus
     `_restore_attempt()`, without touching the ack poll loop, `_decide_from_record` or
     `_liveness_note`;
   - `tests/test_agent_restore.py`;
   - `website/content/docs/workflows/freeze-and-restore-agents.md`: its hunks sit at
     L86-160, while mine are in the "What unverified means" section.

   Its decisions are ground truth. My poll-loop and D3 edits go inside
   `_restore_attempt()` as t2039 leaves it.
   - **Do not edit the three shared files until t2039 has committed them.** The isolation
     problem runs both ways. Even if I never stage a foreign hunk, t2039 staging a whole
     file after I edited it would absorb my additions into its commit. So the gate comes
     before my first edit, not before my commit.
   - **The gate (re-run right before the first edit to each shared file):**
     - `git diff --quiet -- <file>` exits 0 (no uncommitted hunks of anyone's);
     - `git log 989687394..HEAD -- <file>` shows t2039's commit (or t2039 is archived).

     Only then edit, on top of the landed file.
   - **Meanwhile, do all non-overlapping work:**
     - store, wrapper, freeze engine, hook, seed, setup;
     - fixtures and the spike;
     - the other website pages and every other test file.
   - **If the gate still fails when the non-overlapping work is done, stop and ask the
     user.** The choices are to wait for t2039, or to agree an explicit handover saying
     how both writers isolate their changes. Never edit a shared file while it holds
     foreign uncommitted hunks.
   - **Commit:** `git diff --stat` on the staged set must list only t2040 paths. Stage by
     explicit path, never `git add -A`.

1. **Store (`.aitask-scripts/lib/agent_sessions.py`)**
   - `restore_confirm(…, rollout_session: str | None = None, …)`:
     - Keep the existing state, nonce and `launch_pid` checks.
     - Add the D3 `last_error` refusal.
     - With `rollout_session`:
       - require `rec.restore_mode == "resume"` and `rec.agent_kind == "codex"`
         (otherwise `TransitionRefused`);
       - a session that differs from the stored one → persist
         `rec.last_error = f"{nonce}:session_mismatch"` and `raise SessionMismatch(...)`;
       - a match → `_set_location`, `_set_state(LIVE)`, `ack="rollout"`, `last_error=""`,
         `remove_captures`, clear the capture fields, `_clear_lease` →
         `LIVE:<id>|rollout`.
     - Without it, behaviour is unchanged (`ack="liveness"`, captures kept).
   - `main()`: pass `rollout_session=_arg(rest, "rollout-session")`. An empty value is a
     usage error. The existing `SessionMismatch` handler already persists the write
     (`dump`) before it exits 7.
   - `upsert`: implement D2 with a small helper, `_late_restore_ack_ok(rec, pane,
     pane_pid, session_id)`. The `restoring` branch stays byte-for-byte the same.
     - In the ordinary `selected` branch, compare the stored id before and after
       `_apply_upsert_fields`. If it changed (a new non-blank id, or
       `clear_session_id`), set `selected.launch_pid = 0`. This is the D2 window-close
       rule.
   - `lease_take`: before `_mint_lease`, keep `old = rec.op_nonce`. After it, if `old` is
     non-empty and `rec.last_error.startswith(f"{old}:")`, rewrite the prefix to the new
     nonce (the D3 handover). Update the docstring to say why.
   - New helper next to `codex_session_for_pid`: `codex_resume_evidence(rec: dict, pid)
     -> str`. It returns `""` unless `rec["restore_mode"] == "resume"` and
     `rec["agent_kind"] == "codex"`. Otherwise it calls `codex_session_for_pid(pid)` and
     returns the id, or `""` on any miss. It calls the resolver by module-global name, so
     tests can patch `agent_sessions.codex_session_for_pid`.
   - `restore_verdict`: no logic change. `ack == "rollout"` already reads as `"restored"`.
     Rewrite the L1514-1519 comment: liveness is the outcome when nothing proved the
     session, not "the only codex outcome".
   - Comments: L839, L855-857, L1564-1568, L1596-1598 and L1806-1811. The last one must
     say the resolver is also the restore coordinator's evidence on the *resumed*
     process.

2. **Wrapper (`.aitask-scripts/aitask_agent_sessions.sh`)**: add
   `[--rollout-session <sid>]` to the header's verb list and to `usage()`. Add the
   exit-7 wording: it is also raised by a rollout confirm. `cmd_leased` already forwards
   extra arguments, so no dispatch change.

3. **Coordinator (`.aitask-scripts/lib/agent_restore.py`)**
   - New `_rollout_confirm(record_id, rec, nonce, agent_kind) -> RestoreResult | None`:
     1. `sid = agent_sessions.codex_resume_evidence(rec, launch_pid)`. No sid → `None`.
     2. `frozen_ops.pane_location(rec pane)`. If the pid is not `launch_pid` → `None`.
     3. Call `store("restore-confirm", …, "--rollout-session", sid)`.
     4. rc 0 → `_clear_frozen_stamp` and `RestoreResult(ok, "rollout", "RESTORED:<id>|rollout")`.
        rc 6 → `nonce_mismatch`. Any other rc → re-read and `_decide_from_record`, which
        returns `session_mismatch` after exit 7, `hook` after a lost race, or `None` to
        keep polling.
   - Ack poll loop (L965-972): after `_decide_from_record` returns `None`, try
     `_rollout_confirm` and send any result through `_settle`. That makes a mismatch roll
     back, and the stand-in comes back.
   - `_decide_from_record`: treat `state live` with `ack in ("hook", "rollout")` as
     verified success (outcome = the ack value).
   - D3: `_settle` on the refused-confirm re-read.
   - `_liveness_note`: drop the codex-only string and keep the generic
     `" (captures kept: session id unverified)"`. Update the docstring: liveness now means
     "nothing proved the session within the grace" for every agent.
   - Module docstring property 2: add the rollout evidence and the D1 justification.

4. **Reconcile (`.aitask-scripts/lib/agent_freeze.py` `_reconcile_restoring`)**: after
   the ack-grace gate, in the `launch_pid == observed pid` row:
   - first `nonce = lease()`;
   - then `cur = frozen_ops.store_show(record_id)`. If `cur["last_error"]` starts with
     `f"{nonce}:"`, return `_abort_back_to_frozen(observed.pane_id)` (the D3 handover
     re-check);
   - then run `sid = agent_sessions.codex_resume_evidence(rec, observed.pane_pid)`:
   - sid present → `restore-confirm … --rollout-session sid`:
     - rc 0 → `LIVE:<id>|rollout`;
     - rc 7 → `_abort_back_to_frozen(observed.pane_id)`, which keeps the persisted
       mismatch;
     - anything else → `RECONCILE_FAILED`.
   - no sid → the liveness confirm, as today.

   Update the stale comments at L359-362 (`_backfill_agent_string`) and L611-613
   (`_resolve_record`) with the version boundary.

5. **Hook (`.aitask-scripts/aitask_session_hook.sh`)**:
   - Rewrite L27-37: codex 0.163.0 fires SessionStart in the TUI at the first turn, with
     `source=startup`, or `source=resume` after `codex resume`. 0.153.4 fired it under
     `codex exec` only, and the first version that fires it lies in between (not
     bisected). The freeze-time capture (t1804) still covers older codex, a freeze
     before the first turn, and `/new`.
   - Add a comment at the restore-env block (L153-157): a late ack on a settled record
     is upgraded or becomes a plain upsert (D2), never refused.
   - No logic change: the existing `UPSERTED:` sed already stamps on `|restored_late`.

6. **Shared module comments**:
   - `agent_frozen_ops.py` L115-119: a verified ack is the hook's or the rollout's.
   - `monitor/monitor_app.py` ~L3590 and `monitor/minimonitor_app.py` ~L3142: the
     "`ack = "hook"` branch" becomes the verified-ack branches (`hook` / `rollout`).

7. **Setup and seed**:
   - `seed/codex_config.seed.toml` L53-58: replace the LIMITATION block with the version
     boundary.
   - `aitask_setup.sh` L3482: one-line info saying recent codex fires the hook at a
     session's first turn, and older versions only under `codex exec`.

8. **Fixtures (task item 1)**:
   - Re-capture `tests/data/session_hooks/codex_sessionstart.json` live, from an
     **interactive** session. Use the task's method: isolated tmux `-L`, a throwaway
     `CODEX_HOME` with `auth.json` copied in, a trusted scratch project, a
     `.codex/hooks.json` capture hook, and one turn sent with send-keys.
   - Set `_fixture_status: captured` and `_capture_mode: interactive`. Drop `_reason`.
     Record `_agent_version: 0.163.0`, the date, and `_fires_at: first_turn`.
   - Redact per the README contract. Rewrite `_evidence` to record that nothing fired
     before the first turn.
   - `transcript_layout.json` ~L71 (`originator_note`) and README L84-88 / L109-112:
     the codex section becomes `captured`, with the boundary. Replace the refresh-recipe
     line that points at the archived p1705 plan.
   - `tests/test_frozen_standin_spike.sh` Case 6 is the opt-in producer, so a refresh
     reproduces the capture:
     - after launch, wait a bounded few seconds and record whether anything fired
       before a turn;
     - send one prompt with `ait_tmux send-keys`, then `wait_for_payload`;
     - add a verdict `captured_at_first_turn`. Keep `unsupported` for the no-payload
       case, scoped to "after a turn". Fix the L1051 / L1054 finding strings.

9. **Website docs** (current-state prose, with the boundary as a compatibility fact):
   - `workflows/freeze-and-restore-agents.md` L149-169: the outcome table's `restored`
     row now covers "or, for Codex on Linux, the transcript the resumed process holds
     open". Rewrite the L162-165 cause list.
   - `concepts/framework-session.md` L95-102.
   - `commands/setup-install.md` L65.
   - `tuis/frozenagent/reference.md` L101 (the `restore_ack_grace` row) and L113-117.

   Then run `cd website && python3 check_links.py --build`.

10. **Tests that pin the old claim** (rewrite each to the new truth):
    - `test_frozen_restore_verdict.py` L155-156; also **add** `ack=rollout → ("restored", no warn)`.
    - `test_frozenagent_restore_poll_characterization.py` L200-201; add the same rollout
      row.
    - `test_frozenagent_app.py` L1598 (docstring).
    - `test_agent_freeze.py` L708 (docstring).
    - `test_codeagent_resume_session.sh` L32-33 (comment).
    - `test_agent_sessions_transcripts.py` L3-5 (docstring).
    - `test_frozen_standin_spike.sh` L1051 (step 8).
    - `test_agent_sessions_identity.py::test_restore_of_a_non_restoring_record_is_refused`:
      re-point it at a `frozen` record, where the refusal still holds. The live case
      becomes the new D2 tests.

11. **New tests**
    - `test_agent_sessions_transitions.py`:
      - rollout confirm on a match: live, `ack=rollout`, captures deleted, error and
        lease cleared;
      - mismatch: `SessionMismatch`, the error persisted, the record still `restoring`;
      - refused in repick mode, for a non-codex record, and on a `launch_pid` mismatch;
      - D3: a current-nonce `last_error` refuses both the liveness and the rollout
        confirm. A stale-nonce error does not (control);
      - D3 handover:
        - `lease_take` on a stale `restoring` lease rewrites `<N1>:session_mismatch` to
          `<N2>:session_mismatch`;
        - an older-attempt error with a different prefix, and a lease-less (`op_nonce`
          empty) record, are left unchanged;
        - after the takeover, `restore_confirm(nonce=N2)` is refused because of the
          transferred error;
      - CLI: `main([... "restore-confirm", ..., "--rollout-session", wrong])` exits 7
        and the file on disk holds the error.
    - `test_agent_sessions_identity.py` (D2):
      - upgrade on a full binding match (`restored_late`, `ack=hook`, captures deleted);
      - a pid or pane mismatch → plain `updated`, captures kept, ack stays `liveness`;
      - resume with a different session on a live record → `updated`, the new id adopted;
      - `ack=rollout` / `hook` → plain `updated`;
      - **sequential, the review case:** `live/liveness`, target A, matching pid and
        pane. A late hook **B** → `updated`, B adopted, `launch_pid` now 0. A second
        hook **B** → still `updated`, `ack` stays `liveness`, and **A's capture files
        and capture fields survive**. A control with **A** first upgrades to `hook`;
      - an ordinary upsert with `clear_session_id` on a `live/liveness` record also
        zeroes `launch_pid`;
      - a `frozen` record → still refused;
      - `restoring` with a wrong nonce → still `NonceMismatch`.
    - `test_agent_restore.py`: new class `TestRolloutEvidence`. It patches
      `agent_sessions.codex_session_for_pid`, `_reread` and `restore_ack_grace`, and reuses
      `_RecordingStore` / `_ScriptedTmux`.
      - match → `restore-confirm` carries `--rollout-session`, outcome `rollout`, success
        **before** the grace (a large grace that does not elapse);
      - mismatch (store rc 7, re-read shows `<nonce>:session_mismatch`) → `restore-abort`
        plus a rollback respawn;
      - `MISS_NO_MATCH` / `MISS_NO_PROCESS` → liveness fallback, unchanged;
      - claude record and repick mode → the resolver is never called;
      - D3 → refused confirm plus a mismatch on re-read rolls back;
      - `_decide_from_record` reads `live` + `rollout` as success.
    - `test_agent_freeze.py` (reconcile `restoring`): evidence match →
      `LIVE:<id>|rollout`, captures deleted; mismatch → `STANDIN:<id>`, frozen, error
      persisted, no liveness confirm; no evidence → the existing liveness tests still
      pass. Patch the resolver to a miss where the fixture is codex.
      - **The handover race:**
        1. Take the pre-lease snapshot (no error).
        2. Inject `<N1>:session_mismatch` into the store, after the snapshot and before
           lease acquisition.
        3. Pass a lease double whose first call runs the real `lease_take` on a stale
           lease.

        Expect `STANDIN:<id>`, state `frozen`, captures retained, and no
        `restore-confirm` success, with the resolver patched both to a miss
        (liveness path) and to a matching id (rollout path).
    - `test_agent_sessions_contract_call_sites.py` `CALL_SITES`:
      - add `D.restore.4 rollout confirm` and `C.rec restoring + rollout evidence ->
        confirm` (`restore-confirm`, `[nonce, pane, pane_pid, rollout_session]`), plus
        `D.restore.4b late hook ack` (`upsert` on `live`);
      - the state-legality fixture gets `agent_kind = "codex"` and
        `rollout_session="sid-1"` in its kwargs.
    - `test_session_hook.sh`: once the fixture is `captured`, its existing branch asserts
      one upsert and the forwarded session id with no edit. Add one case: an upsert stub
      answering `UPSERTED:<id>|restored_late` still stamps the pane.
    - Live, `test_restore_flows_live.sh` (real store, real coordinator, real hook):
      - New fake `codex` shim: `exec -a codex bash fake_agent.sh "$@"`, so argv0 is
        `codex`.
      - New `fake_agent.sh` knob `FAKE_AGENT_ROLLOUT_DIR`: write
        `rollout-…-<sid>.jsonl` with a `session_meta` first line for the session it runs
        as, and hold it open on fd 9.
      - **Case 14 — codex resume verified by its rollout:** `FAKE_AGENT_NO_HOOK=1` and a
        long grace. Expect `RESTORED:<id>|rollout` well under the grace, captures
        deleted, stamp cleared. The pre-freeze agent also runs through the shim and
        holds the seeded rollout, so the t1804 freeze capture records the id rather
        than clearing it.
      - **Case 15 — late hook after a liveness confirm:** claude-shaped fake with
        `FAKE_AGENT_HOOK_DELAY` greater than the grace. Expect `RESTORED:<id>|liveness`
        first, then the record becomes `ack=hook` with captures deleted, the pane
        carries `@aitask_record`, and the hook log has no `TRANSITION_REFUSED`.

12. **Live check with real codex** (Linux, codex 0.163.0), recorded in Final
    Implementation Notes:
    - Setup: isolated tmux socket; throwaway `AITASKS_AGENT_SESSIONS_FILE` and
      `AITASKS_FROZEN_DIR`.
    - Freeze a codex agent after one turn, then restore it. Expect outcome `restored`
      (`ack=rollout`), captures deleted, and no prompt sent.
    - Then type a turn in the restored agent. Expect no `TRANSITION_REFUSED` in the hook
      stderr, the pane stamped, and the record still `live`.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (read only the last line for the
  verdict), plus the touched modules run directly.
- `bash tests/test_session_hook.sh`, `bash tests/test_codeagent_resume_session.sh` and
  `bash tests/test_restore_flows_live.sh`. Also `bash tests/test_frozen_standin_spike.sh`:
  Case 5a must validate the new fixture.
- `shellcheck .aitask-scripts/aitask_session_hook.sh .aitask-scripts/aitask_agent_sessions.sh .aitask-scripts/aitask_setup.sh`
- `cd website && python3 check_links.py --build`
- `grep -rn "codex exec" .aitask-scripts seed website/content tests/data`: every
  remaining hit carries a version qualifier.
- Step 12's live run.

## Post-implementation (Step 9) follow-ups

- Create the **macOS follow-up task**: the t1821 section verbatim, plus "this also
  extends the t2040 rollout evidence (`codex_resume_evidence`) to macOS". Labels:
  `codex, frozen, session_persistence`.
- `./ait note 1822 --from 2040`: its macOS expectation ("nothing is captured") no longer
  holds on codex ≥ 0.163 with the hook installed.
- No skill files change, so no ports to other agents.
- Step 9: archival, and t1821's folded file is cleaned up.

## Risk

### Code-health risk: medium
- The store state machine changes in three places: the rollout confirm, the late-ack
  path in `upsert`, and the D3 refusal. A defect could delete the only capture on weak
  evidence, or refuse a legitimate ack · severity: medium · → mitigation: none
  (covered by the transition, identity and call-site tests in steps 10-11 and the live
  Cases 14-15)
- A rollout mismatch now **rolls back**, killing the resumed agent, where it used to be
  liveness-confirmed. If a future codex rewrote its rollout id on resume, restores would
  start failing (safely: stand-in back, capture kept) · severity: medium · → mitigation:
  none (ambiguity and absence stay non-verdicts; the step 12 live run pins 0.163.0
  behaviour)
- The doc and comment sweep touches about 20 sites · severity: low · → mitigation: none
  (the grep check in Verification)
- t2039 holds uncommitted hunks in `agent_restore.py`, `test_agent_restore.py` and
  `freeze-and-restore-agents.md` in this same checkout. A careless commit would ship
  them under t2040, and an edit planned against the pre-t2039 shape would conflict ·
  severity: medium · → mitigation: none (step 0: no edit to a shared file until t2039 has
  committed it; non-overlapping work continues meanwhile)

### Goal-achievement risk: medium
- The evidence and the hook timing rest on codex behaviour measured on one version
  (0.163.0). The task itself names a future daemon-routed TUI as a risk to guard:
  - the `/proc` evidence would silently miss, and degrade safely to liveness;
  - the **hook would run with the daemon's environment** — no `TMUX_PANE`, or another
    pane's — and could upsert the wrong pane's record. This plan does not guard that.

  severity: medium · → mitigation: hook_pane_ancestry_guard
- The fixture recapture and the live check need a real codex run with working auth. If
  the live run is unavailable, item 1 cannot be finished as specified · severity: low ·
  → mitigation: none

### Planned mitigations
- timing: after | name: hook_pane_ancestry_guard | type: enhancement | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — a daemon-routed codex TUI would hand the SessionStart hook the daemon's environment (wrong or missing TMUX_PANE) | desc: aitask_session_hook.sh refuses to record unless the pane's #{pane_pid} is an ancestor of the hook process (bounded ppid walk via ps); the hook tests' tmux stub reports an ancestor pid

## Post-Review Changes

### Change Request 1 (2026-10-16 15:45)
- **Requested by user (review findings):**
  1. A late hook from a gone-pane restore's NEW window (no `@aitask_record`, possibly a suffixed window name) fell through to an ordinary upsert that selected by window, and created a second record for an `ack=rollout`/`hook` record.
  2. `setup-install.md` overstated freeze-time capture: there is no rollout before a session's first turn, so an agent frozen then has no session and is re-picked.
  3. (follow-up) `_reconcile_restoring` leaves `@aitask_frozen` on the running pane after a successful confirm. This is pre-existing, and the new rollout branch inherits it.
- **Changes made:**
  1. `agent_sessions.upsert`: on the late fallthrough, a caller in the restored record's own pane with no stamp adopts the restore target as its `id`, and the ordinary rules then update the record and follow the window. A caller in a different pane drops the target. The window-follow logic was extracted into `_follow_window` and is also applied in the late-upgrade branch. It is not applied in the in-grace ack branch, which can fire before the coordinator's rename. Tests: suffixed window × {rollout, hook}, late upgrade in a suffixed window, and a foreign-pane control. Both removal mutants were caught.
  2. Reworded `setup-install.md`, the hook's CODEX TIMING comment and the seed TOML comment: freeze-time capture applies to an older codex (Linux, once a turn has been taken); before the first turn the agent has no session and is re-picked.
  3. Spawned as follow-up **t2045** (`reconcile_clears_frozen_stamp_after_confirm`, bug, `followup_kind: upstream_defect`, anchored to t2040). Its scope is guarded marker cleanup after a successful reconcile confirm, plus freezing the recovered agent again.
- **Files affected:** `.aitask-scripts/lib/agent_sessions.py`, `tests/test_agent_sessions_identity.py`, `website/content/docs/commands/setup-install.md`, `.aitask-scripts/aitask_session_hook.sh`, `seed/codex_config.seed.toml`

### Change Request 2 (2026-10-16 15:55)
- **Requested by user:** the stale frozen-marker follow-up had no linked task ID.
- **Changes made:** created t2045 and linked it above (Change Request 1, item 3).
- **Files affected:** `aitasks/t2045_reconcile_clears_frozen_stamp_after_confirm.md` (new), this plan

## Final Implementation Notes
- **Actual work done:**
  - Implemented D1, D2 and D3 as planned:
    - `restore-confirm --rollout-session` (store, wrapper doc, CLI);
    - `codex_resume_evidence`;
    - the coordinator's `_rollout_confirm` in the ack poll loop, with `_settle` on the refused-confirm re-read;
    - the reconcile evidence row, with a post-lease re-read;
    - the late-ack handling in `upsert`: `_late_restore_ack_ok`, upgrade to `restored_late`, otherwise an ordinary upsert, with the window-close rule;
    - the `lease_take` error handover;
    - the current-nonce `last_error` refusal in `restore_confirm`.
  - Refreshed every stale "codex has no interactive hook / liveness only" claim: code, seed, setup, website and test docstrings.
  - Re-captured `codex_sessionstart.json` from the interactive TUI on codex 0.163.0. It is now `captured`, with `_fires_at: first_turn`; the hook fired 0.37 s after the first prompt and nothing fired before it.
  - Updated spike Case 6 to send a turn and classify `captured_at_first_turn` / `captured_at_launch`.
  - Added the codex shape (argv0 `codex`, rollout on fd 9) to `fake_agent.sh`, plus live Cases 14 and 15.
- **Deviations from plan:**
  - (a) Step 0 coordination with t2039 worked as designed. The three shared-file edits were prepared as scripts and tested in an isolated tree copy, then applied after t2039 committed (302becf93).
  - (b) The two monitor drop-dialog comment edits (step 6) were reverted before commit. t2042 started editing `monitor_app.py` / `minimonitor_app.py` mid-session, so by the plan's own isolation rule my hunks came out. t2042 then committed (4db8fb0af) with no t2040 content. Those comments still name only the `ack = "hook"` branch: incomplete (a rollout confirm also deletes captures), but not wrong.
  - (c) Review round 1 added `_follow_window` and own-pane restore-target adoption, and reworded the freeze-capture claims (Post-Review Changes, Change Request 1).
  - (d) Added a code comment in `lib/agent_string.sh` and a `codex_session_for_pid` docstring note for the daemon finding below.
- **Issues encountered:**
  - The live tmux suites refuse to run inside the user's tmux. They were run fully sandboxed with `env -u TMUX -u TMUX_PANE TMUX_TMPDIR=<private>` (their own `require_isolated_tmux` sets the gateway socket); the user's `-L ait` server was verified untouched after each run.
  - The real-codex live check used a scratch aitasks project (scripts symlinked, metadata copied, the seed hook block), a throwaway `CODEX_HOME` and a private socket. The stand-in viewer exited there (no `ait` dispatcher in the scratch project), so the restore took the gone-pane branch. Even so it returned `RESTORED:…|rollout` in 1.56 s with the default 20 s grace, captures deleted, no prompt sent.
  - After that, typing a turn in the restored agent fired the late hook (resume, same session). The store did an ordinary update, the record stayed `live` with `ack=rollout`, and the pane was re-stamped after its join had been cleared on purpose.
- **Key decisions:**
  - The evidence is caller-reported and store-compared, in the same shape as the hook ack, rather than the store reading `/proc`.
  - Late-ack upgrade binding is `launch_pid` + pane (the nonce is gone after a confirm), and any session change closes the window.
  - Reconcile acts on rollout evidence only after the ack grace, as before.
  - `_liveness_note` is generic now: codex is no longer liveness-only.
- **Measured finding, codex 0.163.0 (daemon routing):** a codex TUI started WITHOUT `-c tui.alternate_screen=never` can be routed through the shared app-server daemon (`$CODEX_HOME/packages/app-server-daemon`). A bare `codex` was daemon-routed; the same launch with only that override held its own rollout, and so do the user's wrapper-launched agents. When daemon-routed:
  - the TUI process holds no rollout;
  - the daemon runs the SessionStart hook with the `TMUX_PANE` of the pane that started it;
  - the framework's own launches are unaffected, because `CODEX_TUI_OVERRIDES` carries the override.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/agent_freeze.py:1266-1281` — after a successful `restore-confirm`, `_reconcile_restoring` never clears the pane's `@aitask_frozen` stamp or attempt mark, so the recovered agent cannot be frozen again (`FREEZE_SKIPPED … already frozen`). Pre-existing; the new rollout branch inherits it. Spawned as t2045.
  - `.aitask-scripts/lib/agent_freeze.py:524` — `_capture_codex_session` treats `MISS_NO_MATCH` as disproving a stored codex id. For a daemon-routed (hand-started) codex the TUI process never holds a rollout, so every freeze clears a valid hook-recorded session id and the restore degrades to re-pick. Measured live on 0.163.0.
  - `.aitask-scripts/aitask_session_hook.sh:52` — the hook trusts `$TMUX_PANE` from its environment. A daemon-routed codex runs the hook with the daemon's `TMUX_PANE`, so a second hand-started codex can upsert another pane's record. Measured live: the daemon's environment had `TMUX_PANE=%1`. This is the planned "after" mitigation `hook_pane_ancestry_guard`, now with concrete evidence.
