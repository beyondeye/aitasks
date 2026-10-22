---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [codex, frozen, session_persistence]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2040
created_at: 2026-10-18 09:39
updated_at: 2026-10-22 08:12
---

## Split from t2040

t2040 merged t1821. At planning time the user chose to split the macOS part back out
into its own task, because this repo's Linux CI cannot live-verify it. Its content
follows verbatim under "Carried over from t1821".

**What t2040 changed that this task must account for:**

- `agent_sessions.codex_session_for_pid` is now ALSO the restore coordinator's verified
  evidence, through `agent_sessions.codex_resume_evidence`. On Linux a resumed codex is
  confirmed as `ack=rollout` from the rollout its process holds open, by
  `agent_restore._rollout_confirm` and by reconcile's `launch_pid` row in
  `agent_freeze._reconcile_restoring`. Giving `codex_session_for_pid` a macOS path
  therefore also turns macOS codex restores from `restored, unverified` into verified
  ones. Keep `MISS_NO_PROCESS` distinct for "could not look": a miss is never a verdict
  for the restore either.
- Codex 0.163.0 fires SessionStart in the interactive TUI at the first turn, so with the
  hook installed macOS gets a session id from the hook too. This task still matters for
  older codex, for `/new` without a hook, and for verifying restores without waiting for
  the hook.
- t2040 measured on Linux that a codex TUI started without `-c tui.alternate_screen=never`
  can be routed through the shared app-server daemon, which then holds the rollout (see
  t2046 and t2047). An `lsof`-based macOS path has the same blind spot. Check whether the
  daemon routing behaves the same on macOS.

## Carried over from t1821


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
