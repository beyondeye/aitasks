---
Task: t1357_5_launch_record_claudecode_enrichment.md
Parent Task: aitasks/t1357_task_workflow_step_stats_and_drift.md
Sibling Tasks: aitasks/t1357/t1357_1_*.md … t1357_7_*.md
Archived Sibling Plans: aiplans/archived/p1357/p1357_*_*.md
Worktree: aiwork/t1357_5_launch_record_claudecode_enrichment
Branch: aitask/t1357_5_launch_record_claudecode_enrichment
Base branch: main
Output branch: main
---

# Plan: t1357_5 — Skillrun launch record + Claude Code transcript enrichment

Task file's Background section pins the transcript-format facts (verify a
sample before relying on field names — formats are upstream-owned and churn).

## Implementation steps

1. **Launch record:** in `aitask_skillrun.sh` and `aitask_codeagent.sh`,
   just before the `exec`, append one JSON line (ts, agent_string, skill,
   profile, pid=$$, cwd) to `.aitask-stats/launches/launches.jsonl`,
   best-effort (`|| true`, mkdir -p guarded). Reuse
   `lib/stats_step_lib.sh` JSON emission (source it defensively — these
   scripts must not gain a hard dependency; guard with a file-exists check).
2. **Session join at capture:** python helper
   `lib/stats_session_join.py` invoked from the capture verb (t1357_1) —
   inputs: repo cwd, run window (manifest started_at → now), launch records.
   Mangle cwd (`/`→`-`) → `~/.claude/projects/<mangled>/`; candidates =
   `*.jsonl` with mtime overlapping the window; pid-anchored match via the
   launch record when present, else newest-overlap. Output: session path +
   `join=pid|window|none`. Record into the `run/end` event's `extra`.
   Failure → `join=none`, non-fatal.
3. **Transcript slicer** `lib/stats_transcript_claude.py`: stream the
   session jsonl; for each `assistant` record accumulate per step window
   (from the run's event timeline): input/output/cache tokens
   (`message.usage`), tool-call counts by `tool_use` name, dominant
   `message.model` + `effort`. Skip sidechain subdirectories in v1. Output:
   `t<id>_<run_id>_enrich.jsonl` (one line per step with sums + provenance
   header line) written beside the per-run event file and committed in the
   same capture commit. When the run's manifest `effort` is `unknown` and
   the transcript has a dominant effort, back-fill it into the run/end dims.
   Raw transcripts are NEVER committed.
4. **Report integration:** `lib/stats_step_data.py` gains an enrichment
   loader (keyed by run id); `aitask_stats.py` step table adds token columns
   rendered only when any enrichment exists.
5. **Docs:** new `aidocs/framework/agent_session_logs.md` — all three
   agents' session-log formats (Claude Code fields used here; Codex rollout
   `task_complete.duration_ms` / `token_count.reasoning_output_tokens` /
   `session_meta` model; OpenCode storage layout, per-message `cost` and
   token splits, session `directory` repo filter) + blind spots (Claude Code
   Web lane, Antigravity CLI, Codex mid-session /model switches). This is
   the follow-up task t1359's starting point.

## Verification

Per task file: python fixture tests (slicing, sums, effort extraction,
malformed tolerance; join pid-beats-window; no-overlap → none), bash
negative control (launches dir unwritable → wrappers still exec), launch
line written before exec (stub binary asserts file exists).
Suite runner last-line verdict only.

## Step 9

Standard Step 9.
