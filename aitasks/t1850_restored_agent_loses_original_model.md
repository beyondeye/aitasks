---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [frozen, model_selection]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-21 22:42
updated_at: 2026-09-22 07:41
---

## Problem

A restored agent does not come back with the model the original agent was using.

Observed on 2026-09-21: record `7b9ad914` (t1687_1, window `agent-pick-1687_1`, launched 2026-09-20T09:30Z through the pick flow, session hook installed) was restored with `R`. The resumed agent came back on a different (default) model.

## Evidence

- The record's `agent_string` (and `agent_kind`) is `''` for **every** record in `~/.config/aitasks/agent_sessions.json`, including e2c4aa8b (t1794_9), which was also hook-recorded.
- `agent_restore.py::build_resume_argv` / `build_repick_argv` pass `agent_string=rec.get("agent_string") or None`. With a blank string, the wrapper resolves the project's default agent/model instead of the original.
- `aitask_codeagent.sh` (invoke path) exports `AITASK_AGENT_STRING` before `exec`, and `aitask_session_hook.sh` passes `--agent-string "${AITASK_AGENT_STRING:-}"`. t1802 (landed 2026-09-14, before this launch) made the store keep non-blank values. So the chain *should* have recorded it. Why it didn't is **not yet determined**. Candidates to check:
  - Pick launches from board/monitor may not go through the `invoke` branch that exports the variable (e.g. a different exec path, or `resolve_agent_string` returning empty).
  - Claude Code may not pass the parent environment through to SessionStart hook processes the way the hook assumes.
  - The upsert argument may be dropped or validated away somewhere between the hook and `_apply_upsert_fields`.

## Fix

1. Reproduce: launch a pick agent with a non-default model, then check the record's `agent_string`.
2. Fix the broken link so the hook-recorded agent string lands in the store.
3. Belt and braces: at freeze time, if the record's agent string is blank, try to recover it from the live process (`/proc/<pid>/environ` `AITASK_AGENT_STRING`, or the `--model` in its argv) before the process is killed. Once frozen, it is unrecoverable.
4. When restoring a record with no agent string, say so in the restore outcome ("restored with default model — original model unknown") instead of silently switching models.
