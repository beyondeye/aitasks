---
Task: t2046_freeze_keeps_hook_session_for_daemon_routed_codex.md
Base branch: main
Output branch: main
---

# t2046 — Daemon-routed codex: the freeze clear is correct after t2047; document the limitation

## Context

The task reported that `_capture_codex_session`
(`.aitask-scripts/lib/agent_freeze.py`) treats `MISS_NO_MATCH` as disproof. For a
daemon-routed (hand-started) codex the TUI process holds no rollout, so every
freeze cleared a valid **hook-recorded** session id.

While this task was in planning, t2047 landed (`00322dab0`). The SessionStart hook
now records **nothing** when a codex app-server daemon sits between the hook and
its pane. That covers every daemon-routed session, the daemon's starting pane
included (`aitask_session_hook.sh` §5b, forms a/b/c). t2047 sent two notes to
this task saying so, and both were verified against main.

Consequences:

- A daemon-routed codex no longer gets a valid hook-recorded id, so the
  `MISS_NO_MATCH` clear has nothing valid to destroy. The bug in the task can no
  longer occur for new agents.
- An id still stored on a daemon-routed pane is stale, or it was written by the
  pre-t2047 hook. That hook ran every routed session's hook as the **first**
  pane, so such an id may hold another pane's conversation.
- The candidate fixes would therefore keep untrustworthy ids:
  - "the hook vouches for the id" has no evidence to act on any more;
  - "the daemon holds the id's rollout" would keep wrong-pane ids, because the
    daemon holds every routed pane's rollout.
- Clearing is now the correct behaviour.
- **Plan review found a hole:** the clear is not universal today. The unstamped
  fallback in `_resolve_record` never runs the capture rules, and it re-sends the
  pane's `@aitask_agent_session`. So a legacy id survives there (reproduced by
  the reviewer). Step 3 closes that path. The "legacy ids are cleared" claim
  holds only after step 3, and only on Linux, where the observation can run. On
  `MISS_NO_PROCESS` (macOS) nothing is cleared, by design.

**User decision:** resolve t2046 as covered by t2047, with no change to the
stamped path's behaviour. Make the unstamped fallback apply the same rules (step
3), fix the stale comments, pin the behaviour with tests, and **document that a
daemon-routed codex still cannot be resumed through freeze/restore** (it is
re-picked). Reliable mapping from a pane to its conversation for daemon-routed
codex is a **separate follow-up task**, so closing t2046 does not imply that this
capability works. The planned live-check mitigation is dropped: there is no new
behaviour to check live.

## Implementation

1. **`.aitask-scripts/lib/agent_sessions.py`** — in the `codex_session_for_pid`
   docstring, replace the paragraph ending "The freeze engine, however, reads
   `MISS_NO_MATCH` as disproving a stored codex id." Its last sentences become:
   since t2047 the hook records nothing for a daemon-routed codex, so a stored
   id on such a pane is stale or comes from the pre-t2047 hook, which reported
   the daemon's starting pane; the freeze clears it, and the agent is re-picked.
   The daemon holds every routed pane's rollout, so its fds cannot attribute a
   conversation to one pane.

2. **`.aitask-scripts/lib/agent_freeze.py`**:
   - In the `_CODEX_DISPROVING_MISSES` comment, add a paragraph saying that
     `MISS_NO_MATCH` stays disproving for a daemon-routed TUI as well (t2046),
     and why: no hook id is recorded for it any more (t2047), and the daemon's
     fds cannot be attributed to a pane.
   - In the `_capture_codex_session` docstring, extend the "DISPROVING miss"
     bullet with the same point in one sentence.

3. **Fix the unstamped fallback in `_resolve_record`
   (`.aitask-scripts/lib/agent_freeze.py`), found in plan review.** When the pane
   has no usable `@aitask_record`, the fallback:
   - seeds `session_id` from the pane's `@aitask_agent_session` whenever the live
     observation misses;
   - upserts without `--id` (the store selects an existing record by pane
     identity);
   - never runs `_capture_codex_session`.

   So a legacy (or wrong-pane) codex id survives a `MISS_NO_MATCH`, both in an
   existing selected record and re-sent from the pane option. It is a real
   path: a dangling or missing stamp falls through to it.

   Two changes, both conditioned so that the legitimate hook fallback stays as
   it is:
   - (a) **Do not feed the pane option** into the upsert when the observation is
     a *codex-proving* disproof: `_miss in (MISS_NO_MATCH, MISS_AMBIGUOUS)`,
     meaning the process is verified codex and its fds disprove any id. The
     pane option still feeds the upsert on `MISS_NO_PROCESS` (macOS, could not
     look) and on `MISS_NOT_CODEX`. In the second case the pane runs another
     agent, e.g. claude, whose hook-stamped id this fallback exists to carry.
   - (b) **After a successful upsert**, when `_miss in _CODEX_DISPROVING_MISSES`,
     run `_capture_codex_session(record_id, frozen_ops.store_show(record_id),
     facts, root)` on the record the upsert actually selected. The unstamped
     path then applies exactly the stamped path's rules: it clears only a
     codex-owned stored id, leaves another agent's record untouched, never
     raises, and never fails the freeze. It costs one extra `/proc` probe on
     that branch only. It runs before `_backfill_agent_string`, matching the
     stamped path's order.
   - Comment the condition with the t2046 rationale.

4. **Tests — `tests/test_agent_freeze.py` `CodexSessionCaptureTests`:**
   - `test_a_daemon_routed_miss_still_clears_a_stored_id` (stamped path):
     - setup: a stored codex id, with the pane's `@aitask_agent_session` equal
       to it (the "hook-vouched" shape a pre-t2047 hook could write for the
       wrong pane);
     - action: observe `MISS_NO_MATCH`;
     - asserts: id and transcript cleared, agent string kept;
     - the docstring names t2047.
   - `test_an_unstamped_pane_clears_a_legacy_id_on_a_codex_miss` (the
     reviewer's repro):
     - setup: blank `@aitask_record`, an existing codex record holding
       `sess-stale` and its transcript, and a pane option equal to `sess-stale`;
     - action: observe `MISS_NO_MATCH`;
     - asserts: the freeze succeeds, the record's id and transcript are cleared,
       the agent string is kept, a `--clear-session-id` upsert was sent, and no
       upsert carried `--session-id sess-stale`.
   - `test_an_unstamped_pane_does_not_resurrect_a_pane_option_id_on_a_codex_miss`:
     - setup: blank stamp, a record with no stored id, and a pane option
       holding a legacy id;
     - action: observe `MISS_NO_MATCH`;
     - assert: no `--session-id` is sent, and the record ends id-less.
   - `test_an_unstamped_non_codex_pane_still_records_its_hook_id`:
     - setup: blank stamp, pane option `sess-abc`;
     - action: observe `MISS_NOT_CODEX` (`is_codex=False`);
     - assert: the fallback upsert still carries `--session-id sess-abc`, and
       the record keeps it. This preserves the legitimate fallback.
   - The existing `test_the_pane_option_still_feeds_the_fallback_upsert`
     (`MISS_NO_PROCESS`) keeps covering macOS.
   - Mutants, run in an isolated copy:
     - drop (a): the "does not resurrect" test fails;
     - drop (b): the legacy-id test fails;
     - widen (a) to `MISS_NOT_CODEX`: the non-codex test fails.

5. **Docs: `website/content/docs/workflows/freeze-and-restore-agents.md`** —
   after "An agent whose CLI cannot resume a session — OpenCode today — can only
   be re-picked.", add the sentence: "So can a Codex agent started by hand that
   Codex runs through its shared app-server daemon: nothing can yet tell which
   conversation belongs to its pane, so no session id is recorded for it (see
   [the SessionStart hook]({{< relref "/docs/concepts/framework-session" >}}#…))."
   Use the real anchor of the hook section in `framework-session.md`, and check
   it with `check_links.py --build`.

6. **Follow-up task (created after approval, Step 7, via
   `aitask_create.sh --batch`):** "Reliable pane-to-conversation mapping for
   daemon-routed codex". Settings: type `enhancement`, priority low, effort
   high, labels `[codex, frozen, session_persistence]`, `anchor: 2040`.
   - Body: the problem, and the evidence (t2040/t2047 measurements; the daemon
     holds every routed rollout; hooks carry the starter's `TMUX_PANE`).
   - Candidate sources to evaluate:
     - the daemon's protocol or `loaded-threads.json`;
     - the client-socket peer of the TUI on `app-server-control.sock` via
       sock_diag;
     - codex exposing the thread id to the TUI process.
   - Acceptance: the hook or the freeze can attribute a session to the pane with
     positive evidence, never by membership alone.

7. Step 9 (Post-Implementation): archival; current-branch mode, no merge.

## Verification

- `python3 -m pytest tests/test_agent_freeze.py tests/test_agent_sessions_transcripts.py -q`.
- Mutant check from step 3, in an isolated copy.
- `cd website && python3 check_links.py --build`.
- Comment- and docs-only edits in `agent_sessions.py` / `agent_freeze.py`: also
  run `python3 -m py_compile` on both.

## Risk

### Code-health risk: low
- One behaviour change, on the unstamped fallback path only (step 3). Both arms
  are conditioned so that `MISS_NO_PROCESS` and `MISS_NOT_CODEX` keep feeding the
  hook's pane option, and each arm is pinned by a test plus a mutant. The rest is
  comments, tests and one doc sentence. t2045, which is in flight, may edit other
  regions of `agent_freeze.py` / `test_agent_freeze.py`, so commits name paths
  only · severity: low · → mitigation: none
- A codex agent that is truly in-process, has taken its first turn, and lost its
  stamp still records its observed id, because the observation wins as before.
  Only an id the live fds disprove is dropped · severity: low · → mitigation: none

### Goal-achievement risk: low
- The task's stated goal (keep the id) is deliberately not delivered: t2047 made
  it unsafe and moot. The user chose to close it, document the limitation, and
  track the real capability as a separate follow-up. Residual: daemon-routed
  codex restores only by re-pick until that follow-up lands · severity: low ·
  → mitigation: follow-up task from step 5

## Post-Review Changes

### Change Request 1 (2026-10-20 10:45)
- **Requested by user (review finding):**
  - The fallback's `_capture_codex_session` call re-probed `/proc`.
  - Sequence: the first read was `MISS_NO_MATCH`, so the upsert omitted the id.
    The second read was `MISS_NO_PROCESS` (the process exited or turned
    unreadable in between). Capture then returned without clearing, so the
    legacy id and transcript survived.
  - Requested fix: keep the first disproof through the invalidation, and add a
    sequential-observation test.
- **Changes made:**
  - `_capture_codex_session` gained an optional `observation` parameter (an
    `_observe_codex_session` result the caller already holds). `_resolve_record`
    passes its own observation through, so there is no re-probe.
  - This is exact: a disproving miss carries no session, so the stored-record
    argument cannot change the decision.
  - New test `test_an_unstamped_pane_keeps_its_first_disproof_through_the_clear`
    returns `MISS_NO_MATCH`, then `MISS_NO_PROCESS`. It is red before the change
    and kills the "drop `observation=`" mutant. The earlier three mutants are
    still killed.
- **Files affected:** `.aitask-scripts/lib/agent_freeze.py`, `tests/test_agent_freeze.py`

## Final Implementation Notes
- **Actual work done:**
  - Re-scoped in planning. t2047 (00322dab0) landed mid-planning and makes the
    hook record nothing for daemon-routed codex, so the task's "keep the id" goal
    became moot and unsafe; the user chose to close it by documenting the
    limitation.
  - Implemented: the stale comments in `agent_sessions.py` / `agent_freeze.py`,
    the unstamped-fallback fix in `_resolve_record` (found in plan review), the
    no-re-probe capture (found in code review), 5 tests, one doc sentence in
    `freeze-and-restore-agents.md`, and follow-up **t2076** (reliable
    pane-to-conversation mapping for daemon-routed codex).
- **Deviations from plan:**
  - Plan review added the unstamped-fallback fix (step 3).
  - Code review added the `observation=` pass-through, so the clear acts on the
    first disproof (Change Request 1).
  - The planned "after" live-check mitigation was dropped with the re-scope:
    there is no new keep-behaviour to check live.
  - Launching a live codex for measurement was refused by the permission
    classifier, so no live run was made in this session.
- **Issues encountered:**
  - Two t2047 notes arrived after the pick and changed the premise. They were
    verified against main (`aitask_session_hook.sh` §5b) and acknowledged.
- **Key decisions:**
  - Rejected both candidate fixes from the task:
    - "hook vouch": after t2047 there is no hook evidence, and a pre-t2047
      stamp may name the wrong pane;
    - "the daemon holds the rollout": the daemon holds every routed pane's
      rollout, so membership is not attribution.
  - Split the disproving misses:
    - `_CODEX_FD_DISPROOFS` (`no_match`, `ambiguous`) also drop the pane stamp
      on the unstamped path;
    - `not_codex` keeps it, because another agent's hook id is valid there.
  - The capture accepts an existing observation instead of re-probing.
  - Static facts (from the 0.163.0 binary and the local `daemon.pid`) are
    recorded in t2076 for the real capability: the control socket path, and
    `processIdentity` = (boot_id, `/proc/<pid>/stat` field 22).
- **Upstream defects identified:**
  - `.aitask-scripts/lib/agent_sessions.py:1951 (codex_session_for_pid, depth-0 only)` + `.aitask-scripts/lib/agent_freeze.py:_CODEX_DISPROVING_MISSES` — a codex typed at a shell prompt in an aitasks pane has the SHELL as its pane pid. The observation therefore returns `MISS_NOT_CODEX`, and the freeze clears a codex id that the hook validly recorded (an in-process TUI passes t2047's ancestry walk). The restore then degrades to re-pick. Found by code reading, not measured live.
