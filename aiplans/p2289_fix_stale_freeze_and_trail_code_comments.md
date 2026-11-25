---
Task: t2289_fix_stale_freeze_and_trail_code_comments.md
Base branch: main
Output branch: main
---

# Plan: t2289 — fix stale freeze / trail code comments

## Context

t2258_9 corrected the website docs on how frozen-agent reconcile runs and on
what feeds a trail's freshness digest. Code comments still carry the old claims,
and a later doc writer could copy them back. This task fixes the comments only.
Nothing changes behaviour.

Re-verified against the current tree. The line numbers in the task have drifted.

- **Reconcile callers:** `reconcile()` (`lib/agent_freeze.py:1800`) runs from
  only two places: the `reconcile` CLI verb (`agent_freeze.py:1983`, reached
  through `aitask_frozen.sh reconcile`) and the monitor maintenance pass
  (`monitor_shared.py:1936`, `_maybe_purge_sessions`). That pass first runs one
  startup grace after construction, then every `_MARKS_PURGE_INTERVAL` (600 s).
  Neither freeze nor restore calls it. The detached `run-shell -b` coordinators
  are `restore` / `drop` (`frozenagent_app.py:977`, `monitor_shared.py:1517`).
- **Codex freeze capture:** `codex_session_for_pid` / `codex_observe_pid` work
  on macOS too. The `ps`/`lsof`/`KERN_PROCARGS2` probe backend was added in
  t2048 (`agent_sessions.py:2038-2063`).
- **Trail digest:** `task_record` (`trail_gather.py:487`) hashes
  `status, depends, gates_pending`, and plan files hash `content_hash`
  (`trail_gather.py:517`). `trail_schema.py:58-75` (the normalization contract)
  and `trail_gather.py:88` say outright that boardidx/timestamps are
  *unrepresentable*, so board repaints are never drift. Leaving the board out
  was intended, so the schema text is what is wrong. The digest stays as it is.

## Changes (comment and description text only)

1. `.aitask-scripts/lib/agent_freeze.py:13-14` (module docstring). Current text:
   "`reconcile` — the §C repair table, run after every freeze, from the monitor
   maintenance tick, and by hand." Change it to: "the §C repair table, run from
   the monitor maintenance pass and by hand (`aitask_frozen.sh reconcile`);
   neither freeze nor restore calls it."

2. `.aitask-scripts/monitor/monitor_shared.py:1891-1893`
   (`_maybe_purge_sessions` docstring). Replace "Reconcile has a second producer
   (the coordinator runs it after every freeze/restore) precisely so retirement
   does not depend on a TUI being open; this call is the opportunistic one."
   with this: reconcile is the recovery for a record left stuck in a
   transitional state. There are exactly two ways to invoke it: this pass,
   which is reconcile's only automatic caller (first run one startup grace
   after construction, then every `_MARKS_PURGE_INTERVAL`), and running
   `aitask_frozen.sh reconcile` by hand. No freeze or restore path calls it.
   A valid startup acknowledgement from the relaunched agent
   (`upsert --restore-of`: the nonce must match, and in resume mode so must the
   previous session id) can settle a `restoring` record directly: the record
   becomes `live` and its lease is cleared. But the agent surviving is not
   enough on its own. Interactive codex sends SessionStart only at its first
   turn. Reconcile checks a pending restore using server-observable evidence,
   takes the lease only before it attempts a repair, and may leave the restore
   pending. Keep the "best-effort / freeze budget" sentences.

3. `.aitask-scripts/aitask_session_hook.sh:67`. Change "(t1804, Linux only)" to
   "(t1804; Linux and macOS since t2048)". The sentence otherwise stays as it
   is.

4. `.aitask-scripts/lib/implementation_trail.schema.json:95`
   (`generation.input_digest.description`). Replace the parenthetical
   "(member/observed task frontmatter subset: status, depends, gates,
   boardcol/boardidx presence, plan-file identity)" with "(each input's kind,
   reference and presence; per task file: status, depends and pending gates;
   per plan file: its content hash. Board column and position are deliberately
   not inputs, so moving a card never stales a trail)". The rest of the string
   stays as it is. `canonical_input_snapshot` (`trail_schema.py:800-831`)
   hashes `kind` and `ref` for every record, so renaming a plan file changes
   the digest even when its contents are identical. That is why the reference
   stays in the description.

5. One extra fix, in the same family as items 1-2:
   `.aitask-scripts/aitask_frozen.sh:9-11` (header). Its example runs
   `run-shell -b "…/aitask_frozen.sh reconcile"` as "how a coordinator that must
   OUTLIVE the pane it respawns gets started". The verbs dispatched that way are
   actually `restore` / `drop`. Change the example to
   `aitask_frozen.sh restore <id>` (and `drop`). Without this the false
   "coordinator runs reconcile" picture survives in the script's own header.

6. `.aitask-scripts/lib/agent_freeze.py:1809-1814` (`reconcile()` docstring).
   This text says no `restoring` record can be produced "until t1705_5 ships
   `restore-begin`'s caller, so those rows are unreachable today". That is
   stale: `agent_restore.py:1031` calls `restore-begin`, so a coordinator that
   dies mid-restore does leave a `restoring` record. Rewrite it to say three
   things. First, the restore coordinator (`lib/agent_restore.py`) creates
   `restoring` records through `restore-begin`. Second, such a record can be
   settled directly by the coordinator's own confirm/abort, or by a valid
   startup ack from the relaunched agent (`upsert --restore-of`: the nonce
   must match, and in resume mode so must the previous session id), which makes
   it `live` and clears the lease. Third, for a restore still pending after
   its coordinator stops, reconcile checks it using server-observable evidence,
   takes the lease only before it attempts a repair, and may leave the restore
   pending. That includes an agent that survived but has not acked yet
   (interactive codex acks only at its first turn). Drop "reconcile is the
   only thing that runs", and drop the "unreachable today" and "writing them
   later" sentences.

6b. `.aitask-scripts/lib/agent_freeze.py:1295-1298` (`_reconcile_restoring()`
   docstring, opening paragraph). It currently says "until t1705_5 lands that
   somebody is the only thing that runs". Rewrite it to say that the restore
   coordinator is `lib/agent_restore.py` and that this function is the repair
   side. It handles a restore still pending after its coordinator stops (no
   confirm/abort ran, and no valid startup ack has settled the record). It
   checks the restore using server-observable evidence, takes the lease only
   before it attempts a repair, and may leave the restore pending. It lives
   here because reconcile owns the whole §C table. The second and third paragraphs (the giving-up branches, the
   positive evidence needed to confirm) stay as they are.

7. `tests/test_agent_freeze.py:2352-2357` (`ReconcileRestoringTests` class
   docstring). Make the same correction: the rows are reachable, because
   `agent_restore.py` calls `restore-begin` and a coordinator that dies leaves a
   `restoring` record. Drop "unreachable in a live run today and the live suite
   cannot cover them". Change "reconcile is the only thing that runs" to say
   that, for a restore still pending after its coordinator stops (no
   confirm/abort ran, and no valid startup ack has settled it), reconcile checks
   it using server-observable evidence, takes the lease only before it attempts
   a repair, and may leave the restore pending. The rest of the docstring (reconcile owns the whole table, the
   giving-up branches, the capture survives) stays as it is.

8. `tests/test_monitor_sessions_purge.py`. Two places carry the old "second
   producer" story:
   - Module docstring, lines 16-20 ("because retirement must not depend on a
     TUI being open, and this is the opportunistic half of that"). Rewrite it to
     say this pass is reconcile's only automatic caller, and that the only other
     route is running `aitask_frozen.sh reconcile` by hand.
   - Assertion message at lines 180-181 in
     `test_it_runs_the_purge_then_the_reconcile`. Change it to something like
     "reconcile must run too — this pass is its only automatic caller (no
     freeze/restore path runs it)".
   The assertions themselves (the expected `names` list and the timeouts) do
   not change.

## Verification

- `python3 -c 'import json; json.load(open(".aitask-scripts/lib/implementation_trail.schema.json"))'`
  confirms the JSON is still valid.
- Run the tests for the touched area:
  `python3 -m pytest -q tests/test_trail_schema.py tests/test_implementation_trail_design.py tests/test_agent_freeze.py tests/test_monitor_sessions_purge.py`,
  plus `python3 -m py_compile` on the four `.py` files.
- Run `shellcheck -x -P SCRIPTDIR .aitask-scripts/aitask_session_hook.sh .aitask-scripts/aitask_frozen.sh`.
  Plain `shellcheck` exits 1 on the existing SC1091 notices about sourced files.
- Re-grep the seven task paths (not the whole repo; `aitask_board.py:4240`
  has an unrelated "unreachable today") for `after every freeze`,
  `t1804, Linux only`, `boardcol/boardidx presence`, `opportunistic half`,
  `second producer`, `unreachable today`, `unreachable in a live run`,
  `only thing that runs`, `until t1705_5` and `relaunched agent survives does
  not`. None of them should match.
- The seven task paths are `.aitask-scripts/lib/agent_freeze.py` (steps 1, 6
  and 6b), `.aitask-scripts/monitor/monitor_shared.py`,
  `.aitask-scripts/aitask_session_hook.sh`,
  `.aitask-scripts/lib/implementation_trail.schema.json`,
  `.aitask-scripts/aitask_frozen.sh`, `tests/test_agent_freeze.py` and
  `tests/test_monitor_sessions_purge.py`. The shared checkout already has
  unrelated modified files, so run `git diff --stat -- <these 7>`, then read the
  hunks of `git diff -- <these 7>` and confirm that only comment, docstring,
  string and assertion-message text changed.

Step 9 (Post-Implementation): commit as
`bug: Correct stale reconcile, codex-capture and trail-digest comments (t2289)`,
then archive the task per the workflow.

## Risk

### Code-health risk: low
None identified. The edits change comment and docstring text, one JSON
description string, and one test assertion message. No assertion or production
logic changes. The schema `description` is not hashed into any digest, and
`NORMALIZATION_VERSION` is unaffected.

### Goal-achievement risk: low
None identified. Every replacement claim was checked against the current code
(callers, cadence constants, the macOS probe backend, the digest record shape).
