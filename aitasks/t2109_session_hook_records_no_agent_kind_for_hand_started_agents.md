---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codex, frozen, session_persistence]
gates: [risk_evaluated]
anchor: 2040
followup_kind: upstream_defect
created_at: 2026-10-21 15:27
updated_at: 2026-10-21 15:27
---

## Origin

Spawned from t2077 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_session_hook.sh:254 — a SessionStart hook run outside the wrapper records the id with a blank agent string (so no agent kind), and a restore then resolves the binary from the project's raw default; a hand-started agent of a kind other than the raw default (e.g. claude in a project whose raw default is codex) would restore with the wrong CLI. Found by code reading; t2077 fixes only the codex side, at freeze time.`

## Diagnostic context

- The hook passes `--agent-string "${AITASK_AGENT_STRING:-}"`. An agent started
  by hand (typed at a shell prompt) has no `AITASK_AGENT_STRING`, and a blank
  agent string is a no-op in the store (t1802), so a new record gets
  `agent_string=""` and therefore `agent_kind=""` (`agent_sessions.py`,
  `_apply_upsert_fields`: the kind is derived from the agent string only).
- `agent_restore.build_resume_argv` passes `agent_string=rec.get("agent_string") or None`
  to `resolve_dry_run_command(root, "raw", …)`, so a blank one resolves the
  project's `raw` default (`claudecode/sonnet5_5` in the shipped config).
- t2077 closed the codex half at FREEZE time: `_capture_codex_session` now
  observes blank-kind records, records `codex/<model>` when a live foreground
  codex proves the id and names a known model, and otherwise clears the id
  (re-pick). Nothing yet handles a blank-kind record whose agent is NOT the
  raw default's kind and is not codex (e.g. a hand-typed claude in a project
  whose `raw` default is codex -> `codex resume <claude-id>`), nor a codex
  record frozen on a host without `/proc`.

## Suggested fix

The hook knows which CLI invoked it (claude and codex install separate hook
configs; the payload shape also differs). Record at least the agent KIND for a
hand-started agent — e.g. pass an `--agent-kind` (or a kind-only agent string)
from the per-agent hook config — and have `build_resume_argv` refuse
(`no_session`/re-pick) rather than fall back to `raw` when the record's kind is
blank or disagrees with the raw default. Measure the hook payload for both CLIs
first.
