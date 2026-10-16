---
priority: medium
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [codex, frozen, session_persistence]
gates: [risk_evaluated]
folded_tasks: [1821]
created_at: 2026-10-16 11:43
updated_at: 2026-10-16 11:43
---

## Origin

Exploration on 2026-10-16 (codex-cli 0.163.0, Claude Code 2.1.300, Linux),
started from "the latest codex has better `codex resume` support — does that
improve resuming frozen agents?". Line numbers below are as of aitasks
`989687394` and may drift.

## Current state

- **Claude Code — complete.** The SessionStart hook records the session id at
  launch. Restore runs `claude --model <id> --resume <sid>`, and the resumed
  agent's hook (`source=resume`, same id) acknowledges it. That gives
  `ack=hook`, so the record is `restored` and its captures are deleted.
- **Codex — partial.** Restore runs `codex resume <sid> -c … --model <id>`
  (`aitask_codeagent.sh` ~L591-595). The session id is captured only at
  freeze time, from the rollout the pane's codex process holds open
  (`agent_sessions.codex_session_for_pid`, t1804). That works on Linux only,
  and only after the agent's first turn. Every restore ends on the liveness
  fallback (`ack=liveness`, "restored, unverified — capture kept"), because
  interactive codex fired no SessionStart (measured on 0.153.4, t1705_1).
- **New in 0.163 `codex resume`** (accepts a session *name* as well as a UUID,
  plus `--include-non-interactive`). This is marginal for us: the store keeps
  UUIDs, and 0.163 has no launch flag for naming a session.

## What changed: measured live on codex 0.163.0

Measured in an isolated tmux server (`-L codexprobe`) with a throwaway
`CODEX_HOME`, plus one run against the real home. Positive control:
`codex exec` fires the project `[hooks] SessionStart` (same TOML shape as
`seed/codex_config.seed.toml`).

1. **Interactive codex now fires SessionStart.** It fires at the **first
   turn**, not at launch. It runs from the pane's own codex process
   (ppid = pane pid) with the correct `TMUX_PANE`, and the payload has
   `source:"startup"` plus `session_id`, `transcript_path`, `cwd`, `model`
   and `permission_mode`. Nothing fires before the first turn.
2. **The real hook works end-to-end.** `.aitask-scripts/aitask_session_hook.sh`
   was run with `AITASKS_AGENT_SESSIONS_FILE` pointing at a throwaway store
   outside `/tmp` and a window named `agent-pick-42`. It created a `live`
   record: `agent_kind=codex`, the correct `codeagent_session_id` (equal to
   the rollout's), `operation=pick`, `task_id=42`. It stamped both
   `@aitask_record` and `@aitask_agent_session`. The hook is not sandboxed.
   Production agrees: a real `agent-pick-158` codex agent (thinking_backend,
   2026-10-16 08:27Z) was recorded by the installed hook.
3. **`codex resume <sid>` fires SessionStart only after the resumed session's
   first turn** (`source:"resume"`, same id). Nothing fires at launch, so no
   ack can arrive within `restore_ack_grace` unless the user types.
4. **A resumed codex holds its rollout open from launch, before any turn.**
   `codex_session_for_pid(<resumed pid>)` returned the expected sid with no
   prompt sent (t1804 measured the same on 0.154).
5. **TUI launches in tmux run in-process.** This holds for both bare `codex`
   and the `CODEX_TUI_OVERRIDES` launch: each holds its own `state_5.sqlite`
   and has no peer on the `/tmp/codex-daemon-<uid>/…` socket, so the
   t1804 /proc capture still works on 0.163. 0.163 does ship a shared
   app-server daemon (`daemon_auto_start` is stable; `codex agents` and the
   IDE app-server use it). **Risk to guard:** if a future codex routes the TUI
   through that daemon, threads (and therefore rollout fds and hook execution)
   would move into the daemon process. The /proc capture would then silently
   miss, and the hook would see the daemon's environment: no `TMUX_PANE`, or
   the `TMUX_PANE` of whichever pane started the daemon.

The codex version that first fires interactive SessionStart lies somewhere in
(0.153.4, 0.163.0]. It was not bisected. Not tested: whether `/new` in the
codex TUI fires SessionStart. The freeze-time /proc capture still covers
`/new`.

## Goal

Make Codex freeze/restore match Claude's wherever codex can now prove the
session. Keep the existing paths for older codex and for platforms without
`/proc`.

## Scope

### 1. Refresh the record, and fix every claim that is now stale

- Re-capture `tests/data/session_hooks/codex_sessionstart.json` from an
  **interactive** session, following the refresh recipe in
  `tests/data/session_hooks/README.md`: `_fixture_status: captured`,
  `_capture_mode: interactive`, drop `_reason`, and record the codex version
  and the first-turn timing. Also update `transcript_layout.json` ~L71 and
  README ~L84-88 / L109-112.
- Fix the claims that "Codex SessionStart does not fire in the interactive TUI"
  or "a codex restore can only reach liveness". State the version boundary
  instead, and keep the old behaviour described for older codex. Known sites:
  - Code:
    - `aitask_session_hook.sh` L27-37
    - `lib/agent_restore.py` L1010-1020 (`_liveness_note` and its string)
    - `lib/agent_sessions.py` L1516-1517, L1564-1568, L1809-1811 ("by
      restore time the process is gone")
    - `lib/agent_freeze.py` L359-362, L611-613
    - `lib/agent_frozen_ops.py` L115-119
  - Setup and docs:
    - `seed/codex_config.seed.toml` L53-58
    - `aitask_setup.sh` L3482
    - `website/content/docs/commands/setup-install.md` L65
    - `website/content/docs/workflows/freeze-and-restore-agents.md` L162-165
    - `website/content/docs/concepts/framework-session.md` L101-102
  - Tests that pin the old claim, to update alongside the behaviour:
    - `test_frozen_restore_verdict.py` L155-156
    - `test_frozenagent_restore_poll_characterization.py` L200-201
    - `test_frozenagent_app.py` L1598
    - `test_agent_freeze.py` L708
    - `test_codeagent_resume_session.sh` L32-33
    - `test_agent_sessions_transcripts.py` L3-5
    - `test_frozen_standin_spike.sh` L1051
- `aidocs/framework/live_endpoint_resolution.md` and
  `live_delivery/agents.txt` are untouched by this (t1706 owns them).

### 2. Verified Codex restore from the resumed process's open rollout

Today a restore settles in the ack poll loop (`agent_restore.py` ~L963-971).
On timeout it falls back to `restore-confirm`, which hardcodes
`ack="liveness"` and keeps the captures (`agent_sessions.py` L1087-1115).
Captures are deleted **only** in the hook ack branch of `upsert`
(L831-864, `ack="hook"`).

Proposal: for `agent_kind == "codex"` in `resume` mode, have the coordinator
accept `agent_sessions.codex_session_for_pid(launch_pid)[0] == expected sid` as
verified evidence (Linux). This needs:

- **A new store verb, or an evidence option on `restore-confirm`.** It would
  record a distinct ack value (e.g. `rollout`), delete captures as the hook
  branch does, and keep the nonce/state/`launch_pid` checks. Reusing
  `upsert --restore-of` would mislabel the evidence as `hook`.
- **Matching updates elsewhere:**
  - `_decide_from_record` (L1023-1071): today it knows only `hook` and
    `liveness`, so an unknown ack would poll and then fail as
    `confirm_refused`.
  - `restore_verdict` (`agent_sessions.py` L1514-1519).
  - The verb dispatch in `aitask_agent_sessions.sh` (~L330-336).
  - `tests/test_agent_sessions_contract_call_sites.py` `CALL_SITES` (~L106-113).
- **Reconcile's liveness row** (`agent_freeze.py` ~L1234-1247) for a
  coordinator that died: the same evidence check, otherwise liveness as today.
- **This is a deliberate policy change.** Comments at `agent_restore.py`
  L22-27, `agent_sessions.py` L855-857 and `agent_frozen_ops.py` L117-118
  say that only the hook counts as evidence. Justify the change in the plan.
  Possible argument: argv0 is verified as codex inside
  `codex_session_for_pid`, and a resume that silently started a fresh
  session would hold a *different* rollout id, so a mismatch still aborts.
- **Tests.** Patch `agent_sessions.codex_session_for_pid` in
  `tests/test_agent_restore.py`, which already fakes `ops.store`, `_reread`
  and `restore_ack_grace`. A live test would need a fake agent whose argv0
  basename is `codex` and which holds `rollout-*-<sid>.jsonl` open;
  `tests/lib/fake_agent.sh` does neither today.

Side observation, to be confirmed in planning: `restore_confirm` does not check
`last_error`, so a `session_mismatch` that lands between the last poll and
`restore-confirm` could still be confirmed. The refused-confirm re-read also
returns without `_settle` (`agent_restore.py` L1000-1002).

### 3. The late `source=resume` hook

The restored agent still carries `AITASK_RESTORE_RECORD`/`NONCE`. When its hook
finally fires at the user's first turn, `upsert --restore-of` hits
`_require_state(…, STATE_RESTORING)` on a record that is already `live` and is
refused (`TRANSITION_REFUSED`, exit 5, nothing written). The pane is then not
re-stamped, and per the code every later SessionStart in that process (e.g.
`/new`) is refused the same way (not tested). Decide in planning which way to
go:

- accept a late, matching resume ack on a `live` + `ack=liveness` record with
  the same nonce (upgrade to verified and delete captures), or
- make the late hook fall through to a plain upsert.

Either way the hook must stop being refused.

### 4. macOS (merged from t1821, below)

On codex versions that fire interactive SessionStart, the hook already gives
macOS a session id at the first turn. t1821's `lsof`/`ps` fallback for
`codex_session_for_pid` remains useful for older codex, for `/new` without a
hook, and for extending item 2's evidence check to macOS. It is in scope as the
lower-priority last step and may be split out at planning time if the task
grows too large.

## Out of scope (separate tasks if wanted)

- **Claude `--session-id` pre-assignment.** Research verdict: worth it only as
  a narrow Linux fallback, minting the id in `build_invoke_command`'s
  claudecode branch and having the freeze engine read it from
  `/proc/<pid>/cmdline` when the hook left no id (t1849, a freeze before the
  hook). It does not help restore acks (Claude's already work), the `/clear`
  gap (the hook matcher is `startup|resume`), or macOS.
- **The board's resume action calls `invoke resume`**
  (`board/aitask_board.py` ~L5300, L5372), but `resume` is not in
  `SUPPORTED_OPERATIONS`. Confirmed: `aitask_codeagent.sh --dry-run invoke
  resume 42` → "Unknown operation: 'resume'".

## Related

- t1822 (manual verification of t1804): its macOS item ("nothing is captured")
  will no longer hold on codex ≥ the hook version once the hook is installed.
  Adjust its expectation when this lands.
- t1842: manual verification of the frozen store/viewer.

## Verification

- Unit: the new ack path (match, mismatch, no rollout, not codex,
  no `/proc`), `restore_verdict`, reconcile's evidence row, the late-hook
  handling, and the store verb contract.
- Live (Linux, codex ≥ 0.163): freeze a codex agent after one turn, restore it,
  and check the outcome is `restored`, the captures are deleted, and no prompt
  was sent. Then type a turn in the restored agent: no `TRANSITION_REFUSED`,
  and the pane is stamped.
- Docs: no remaining "codex fires the hook only under `codex exec`" claim
  without a version qualifier.

## Merged from t1821: codex session capture on macos


## Origin

Deferred from t1804 by explicit user decision at planning time ("Linux /proc
only, plus spawn a follow-up for macOS").

## Goal

Give `agent_sessions.codex_session_for_pid()` a macOS path, so freezing a codex
agent there captures its session id instead of always degrading to re-pick.

## Current state (t1804)

The resolver reads `/proc/<pid>/fd` and `/proc/<pid>/cmdline`. On a platform
with no `/proc` both reads fail and it returns `MISS_NO_PROCESS`, which is
deliberately **absence of evidence**: the freeze engine records nothing and,
critically, **clears nothing** — clearing on that reason would wipe a valid
hook-captured `codex exec` id on every macOS freeze. So macOS behaves exactly as
it did before t1804; nothing is broken there, it just never captures.

Two `/proc` readers would need a macOS equivalent:

- `codex_session_for_pid` — the open `rollout-*.jsonl` file descriptor;
- `codex_process_model` — argv0 (is this really codex?) and the `-m` cli id.

## Suggested approach

`lsof -n -P -Fn -p <pid>` lists open files, and `ps -p <pid> -o args=` gives the
argv — the same two facts. `monitor_core._is_companion_process` is the in-repo
precedent for exactly this shape (read `/proc`, fall back to `ps`).

Points to get right, all load-bearing in the current design:

- **Keep "could not look" distinct from "looked, and it is not codex".**
  `MISS_NO_PROCESS` vs `MISS_NOT_CODEX` decides whether a stored session id is
  left alone or cleared. If `lsof` is absent or refuses, that is `no_process`.
- **Do not let a macOS path change Linux behaviour** — `/proc` stays the primary
  rung.
- `lsof` can be slow; freeze runs on a keypress path, so bound it with a short
  timeout (the existing `ps` fallback uses 2s).

## Verification

`tests/test_agent_sessions_transcripts.py` drives the Linux path through a fake
`proc_root`; the macOS path needs the same treatment — an injectable command
runner rather than a real `lsof` — plus a live check on an actual Mac, which is
the part this repo's Linux CI cannot do.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1821** (`t1821_codex_session_capture_on_macos.md`)
