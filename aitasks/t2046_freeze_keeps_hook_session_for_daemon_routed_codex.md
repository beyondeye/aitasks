---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [codex, frozen, session_persistence]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2040
followup_kind: upstream_defect
created_at: 2026-10-16 16:56
updated_at: 2026-10-19 08:04
---

## Origin

Spawned from t2040 during Step 8b review. Measured live on codex 0.163.0, on Linux.

## Upstream defect

- `.aitask-scripts/lib/agent_freeze.py:524` — `_capture_codex_session` treats
  `MISS_NO_MATCH` as DISPROVING a stored codex session id. For a daemon-routed
  (hand-started) codex the TUI process never holds a rollout, so every freeze clears a
  valid hook-recorded session id, and the restore degrades to re-pick.

## Diagnostic context

Codex 0.163.0 can route its TUI through a shared app-server daemon
(`$CODEX_HOME/packages/app-server-daemon/...`). Measured in t2040's live check, with
an isolated tmux server and a throwaway CODEX_HOME:

- A bare `codex` launch was daemon-routed. Its process held NO `rollout-*.jsonl`
  after a turn, and the daemon process held it. The same launch with only
  `-c tui.alternate_screen=never` ran in-process and held its own rollout.
- The framework's wrapper launches always pass that override (`CODEX_TUI_OVERRIDES`
  in `lib/agent_string.sh`), so wrapper-launched agents are unaffected. A codex
  started by hand in an aitasks pane is.
- Observed sequence:
  1. A daemon-routed agent took a turn.
  2. The SessionStart hook recorded its session (record `live`, correct id,
     `@aitask_agent_session` stamped).
  3. `aitask_frozen.sh freeze` returned `FROZEN:<id>`, but the record's
     `codeagent_session_id` was now EMPTY: `codex_session_for_pid` returned
     `MISS_NO_MATCH`, which `_CODEX_DISPROVING_MISSES` treats as disproof, so the
     freeze ran `--clear-session-id`.
  4. A restore is then refused as `no_session`, and only re-pick works.

t1804 chose "clear on no_match" for a good reason: a `/new` in the TUI before its next
turn, or a recycled pane, leaves the stored id stale, and resuming a stale id replays
the wrong conversation. So `MISS_NO_MATCH` is ambiguous between two cases:

- "the process is in no conversation yet" (stale id: clear it);
- "the process is daemon-routed and holds nothing itself" (valid id: keep it).

## Suggested fix

Make the miss distinguish the two cases rather than dropping the clear. Candidates to
evaluate in planning:

- detect daemon routing on the process (for example its connection to the daemon's
  socket under `$CODEX_HOME`), and report that as a distinct non-disproving miss;
- let positive hook evidence outrank absent fd evidence: when the pane's
  `@aitask_agent_session` (stamped by the hook at every SessionStart) equals the stored
  id, a `MISS_NO_MATCH` does not clear it.

Weigh both against the `/new` staleness case. Interactive codex 0.163.0 fires
SessionStart at the first turn, but whether `/new` fires it is untested. Also note:
the daemon runs hooks with the `TMUX_PANE` of the pane that started it, which the
`hook_pane_ancestry_guard` follow-up of t2040 addresses. The two fixes interact.

## Verification

- Unit: `tests/test_agent_freeze.py` `CodexSessionCaptureTests`, a daemon-routed miss
  with a hook-vouched stored id keeps the id; the `/new`-style stale case still
  clears.
- Live: a hand-started codex with the hook installed, one turn, then freeze; the
  record still carries its session id.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2047** id=2026-10-19T12:46:57Z.d5fc69228fc1f733ddc617ac from=t2047 from_verified=yes at=2026-10-19T12:46:57Z base=bf32b336c0b0673eccba125bf097df173405e8d7 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2047 (hook_pane_ancestry_guard). As of writing this change is NOT yet committed; treat it as pending until a `(t2047)` commit lands on main.
> | 
> | What changes for t2046: after t2047, the SessionStart hook (.aitask-scripts/aitask_session_hook.sh) records NOTHING for a daemon-routed (hand-started, no tui.alternate_screen=never) codex. That includes the daemon's own starting pane. It refuses when the pane's #{pane_pid} is not an ancestor of the hook, or when any hop between them is the codex app-server daemon (exe under $CODEX_HOME/packages/app-server-daemon/, or the process declared by $CODEX_HOME/app-server-daemon/daemon.pid with matching bootId + startTicks, or argv0 codex + argv element `app-server`).
> | 
> | So for a daemon-routed codex:
> | - there is no hook-recorded codeagent_session_id and no @aitask_agent_session stamp for its pane;
> | - your "hook-vouched stored id outranks MISS_NO_MATCH" candidate would have no evidence to act on. The MISS_NO_MATCH clear then has no valid hook id to destroy for these agents.
> | 
> | Measured live 2026-10-19, codex 0.163.0, Linux, isolated tmux:
> | - The daemon is a direct CHILD of its starting pane's codex (setsid, not reparented) while that codex lives. It is reparented to systemd --user after.
> | - The daemon ran a SECOND pane's hook with TMUX_PANE of the FIRST pane.
> | - An in-process codex (CODEX_TUI_OVERRIDES) runs its hook as a direct child of the pane process. It is still recorded.
> | 
> | Evidence lives in t2047's plan (aiplans/p2047_hook_pane_ancestry_guard.md, Final Implementation Notes). Weigh it in your own planning; this note asks for nothing.

> **✉ note:t2047** id=2026-10-19T13:49:17Z.b09685ecba16efd461b2aaf0 from=t2047 from_verified=yes at=2026-10-19T13:49:17Z base=00322dab07d801510541d6f0353f10f51416c198 base_branch=main dirty=yes host=omg16
>
> | Follow-up to note 2026-10-19T12:46:57Z.d5fc6922: the t2047 change it describes (daemon-routed codex hooks record nothing) has now landed on main as 00322dab0. Its form c was narrowed in the end to the daemon's own invocation (argv0 codex, argv[1] app-server, plus a later --managed-daemon). Advisory only.
