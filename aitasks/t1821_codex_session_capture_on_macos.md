---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [codex]
gates: [risk_evaluated]
anchor: 1797
followup_kind: carry_over
created_at: 2026-09-16 18:09
updated_at: 2026-09-16 18:09
---

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
