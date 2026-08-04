---
priority: medium
effort: medium
depends: [1357]
issue_type: feature
status: Ready
labels: [reporting, codeagent]
gates: [risk_evaluated]
anchor: 1357
created_at: 2026-07-31 10:59
updated_at: 2026-07-31 10:59
boardidx: 113664
---

## Context

Deferred follow-up of t1357 (per-step execution stats for task-workflow),
created at decomposition time as an explicit follow-up task (user decision:
Claude Code enrichment first — t1357_5 — with Codex/OpenCode as a tracked
follow-up). Blocked on the t1357 family landing (`depends: [1357]`).

t1357_5 delivers: the launch record from `aitask_skillrun.sh` /
`aitask_codeagent.sh`, the session-join logic at capture time, the Claude
Code transcript slicer (`.aitask-scripts/lib/stats_transcript_claude.py`),
the committed enrichment sidecar format
(`aitasks/metadata/stats/events/<YYYY-MM>/t<id>_<run_id>_enrich.jsonl`), and
`aidocs/framework/agent_session_logs.md` documenting all three agents'
session-log formats. This task ports the slicer to the other two agents.

Note: t1357_7 (retrospective) re-prioritizes this task against real usage —
check its findings before implementing.

## Scope

- **Codex slicer:** parse `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` —
  `event_msg.token_count` (`reasoning_output_tokens` broken out — feeds the
  effort/reasoning dimension), `task_started`/`task_complete`
  (`duration_ms`, `time_to_first_token_ms` — free per-turn wall clock),
  model from `session_meta`/`turn_context` (more reliable than Codex
  self-report, which is blind to mid-session /model switches).
- **OpenCode slicer:** parse `~/.local/share/opencode/storage/` —
  session `directory` field filters to this repo; per-message
  `time.{created,completed}`, `tokens.{input,output,reasoning,cache}`, and
  USD `cost` (the only agent with pre-computed dollar cost — add a cost
  column to the enrichment sidecar schema if absent).
- Extend the session-join logic for both agents' session stores (launch
  record pid + time-window, same confidence provenance as t1357_5).
- Same sidecar output format; report columns appear automatically via the
  t1357_4/`stats_step_data.py` loader.
- Update `aidocs/framework/agent_session_logs.md` with implementation notes.

## Verification

- Python tests with small synthesized fixture files for both formats
  (mirror t1357_5's test structure): slicing, token/cost sums, join
  confidence, malformed-line tolerance. Real-platform semantics per
  `feedback_real_platform_semantics_over_fake_shaped_tests` — fixture shapes
  copied from real log excerpts, including pagination/multi-record realities.
