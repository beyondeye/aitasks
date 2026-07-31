---
priority: medium
effort: medium
depends: [t1357_4]
issue_type: feature
status: Ready
labels: [reporting, codeagent]
gates: [risk_evaluated]
anchor: 1357
created_at: 2026-07-31 10:58
updated_at: 2026-07-31 10:58
---

## Context

Fifth child of t1357. Adds the enrichment layer: a launch record from the
headless wrappers (the deterministic anchor joining a workflow run to an
agent session), and a Claude Code transcript slicer that sums tokens /
tool-calls / reasoning-effort per step window. Codex/OpenCode parsers are an
explicit follow-up top-level task (already created at decomposition) — this
child only documents their formats.

Parent plan: `aiplans/p1357_task_workflow_step_stats_and_drift.md`
(child t1357_5 section). Depends on t1357_1..4.

## Background facts (from exploration — verify still true)

- Claude Code transcripts: `~/.claude/projects/<mangled-cwd>/*.jsonl`
  (cwd path-mangled, `/`→`-`). `assistant` records carry `timestamp` (ISO
  ms), `message.model`, `effort`, `attributionSkill`, `message.usage`
  (input/output/cache tokens incl. 5m/1h ephemeral split), and
  `message.content[]` `tool_use` blocks (names → tool-call counts).
  `user` records carry `toolUseResult`. Sidechain sessions live in a
  subdirectory named after the parent session uuid.
- `aitask_skillrun.sh` (~line 125 agent-string default, ~135 profile
  resolve) and `aitask_codeagent.sh` (exports `AITASK_AGENT_STRING`,
  `exec`s the CLI) currently emit ZERO telemetry.
- Codex rollouts: `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`
  (`task_complete.duration_ms`, `time_to_first_token_ms`,
  `token_count.reasoning_output_tokens`; model in `session_meta`).
- OpenCode: `~/.local/share/opencode/storage/` (per-message USD `cost`,
  `tokens.{input,output,reasoning,cache}`, `time.{created,completed}`,
  session `directory` field filters to a repo).

## Deliverables

1. **Launch record:** `aitask_skillrun.sh` + `aitask_codeagent.sh` append a
   JSON line (ts, agent_string, skill, profile, pid, cwd) to
   `.aitask-stats/launches/launches.jsonl` (git-ignored; machine-local;
   best-effort `|| true`). No behavior change otherwise — these scripts
   `exec` the CLI, so the record is written BEFORE exec.
2. **Session join at capture:** extend the capture verb (t1357_1) or a
   python sidekick to record, in the per-run event file's `run/end` extra,
   the best-match Claude Code session id: newest
   `~/.claude/projects/<mangled-cwd>/*.jsonl` whose mtime window overlaps
   the run window, cross-checked against the launch record pid when the run
   was skillrun-launched. Record join confidence
   (`join=pid|window|none`) — provenance so a bad join is discardable.
3. **Transcript slicer:** new `.aitask-scripts/lib/stats_transcript_claude.py`
   — given a session jsonl + the run's step timeline, sum per step window:
   input/output/cache tokens, tool-call counts by tool name, dominant
   `model`/`effort` (also back-fills `effort` into the run's dims when the
   stamped value is `unknown`). Writes an enrichment sidecar
   `aitasks/metadata/stats/events/<YYYY-MM>/t<id>_<run_id>_enrich.jsonl`
   (committed; raw transcripts are NEVER committed). Invoked from capture
   when a join exists; failure is non-fatal.
4. **Report integration:** `lib/stats_step_data.py` loads enrichment
   sidecars when present; `ait stats` step table gains token columns
   (rendered only when enrichment data exists).
5. **Docs:** new `aidocs/framework/agent_session_logs.md` documenting all
   three agents' session-log formats (content from the exploration survey;
   include the Codex/OpenCode details above for the follow-up task) and the
   blind spots: Claude Code Web lane (no local transcript), Antigravity CLI
   (no known session store), Codex mid-session /model switches.

## Verification

- Python tests with a fixture transcript jsonl (synthesized, small): slicing
  by step windows, token sums, tool-call counts, effort extraction,
  malformed-line tolerance.
- Join logic test: fixture launch record + two candidate session files →
  pid-anchored join wins; no-overlap → `join=none` and no enrichment.
- Bash: skillrun/codeagent still function with launches dir unwritable
  (negative control), and the launch line is written before exec (assert
  file exists after a `--dry-run`-style invocation or with a stub binary).
