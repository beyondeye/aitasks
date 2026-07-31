---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, reporting, verifiedstats, gates]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1357_1, t1357_2, t1357_3, t1357_4, t1357_5, t1357_6, t1357_7]
created_at: 2026-07-31 10:44
updated_at: 2026-07-31 11:00
---

## Goal

Add structured, per-step/substep execution statistics for the aitask-pick +
task-workflow critical path, dimensioned by **code-agent**, **LLM model**, and
**model reasoning effort**, with **week-over-week and month-over-month drift
reporting** (which workflow steps are getting slower or faster over time).

Per-run totals are explicitly NOT the unit of analysis — per-step and
per-substep timings are. Capture must be deterministic in-workflow
instrumentation (helpers stamping events), not tmux scrollback capture.
Stats capture runs at the end of an aitask-pick execution (task-workflow
Step 9b territory, alongside the existing satisfaction-feedback hook).

## Agreed design decisions (from exploration)

- **Storage: append-only event log** as source of truth — e.g. monthly JSONL
  files under the task-data branch (`aitasks/metadata/stats/` on
  `.aitask-data`), committed like other metadata. Reports aggregate at read
  time, so drift windows are arbitrary (week-over-week AND month-over-month).
  Rolling-bucket counters (verifiedstats-style, only 1 month of history) were
  rejected as the primary store; optionally usable later as a display cache.
- **Backbone: deterministic helper instrumentation.** Six existing helpers
  already fire at claim→plan→approve→review→merge→archive boundaries and can
  stamp events without touching skill text: `aitask_pick_own.sh` (claim),
  `aitask_gate_record.sh` (plan_approved / risk_evaluated / review_approved /
  build_verified / merge_approved), `aitask_plan_externalize.sh` (plan
  written), `aitask_archive.sh` (done), `aitask_usage_update.sh` (workflow
  end), `aitask_lock.sh` (claim timestamp).
- **Gap spans need explicit stamp lines in skill markdown** (no deterministic
  helper at their boundary): implementation body start/end (largest
  un-instrumented span, WF Step 7 body), review-loop iterations (Step 8 "Need
  more changes" loop), risk-evaluation begin/end, EnterPlanMode→ExitPlanMode
  plan-write span, env/branch setup under no-worktree profiles.
- **Reasoning-effort dimension is new** — nothing in the framework records it
  today (agent strings are only `<agent>/<model>`; no wrapper passes an
  effort flag). It is recoverable from session logs only for Claude Code
  (transcript `effort` field); for Codex/OpenCode the stamp helper must
  record it explicitly (or record `unknown`). Extending
  model-self-detection / `AITASK_AGENT_STRING` conventions is in scope.
- **Transcript enrichment is a follow-up layer, not the backbone**: all three
  agent CLIs leave rich local session logs that nothing reads today —
  Claude Code `~/.claude/projects/<mangled-cwd>/*.jsonl` (per-turn token
  usage, `model`, `effort`, `attributionSkill`, tool_use names), Codex
  `~/.codex/sessions/.../rollout-*.jsonl` (per-turn `duration_ms`,
  `time_to_first_token_ms`, `reasoning_output_tokens`), OpenCode storage
  (per-message USD `cost`, token splits, per-message duration). Joining a
  workflow run to its transcript deterministically requires a **launch
  record emitted by `aitask_skillrun.sh` / `aitask_codeagent.sh`** (agent
  string, skill, profile, pid, session id where obtainable) — today those
  wrappers emit zero telemetry.
- **Cheap deterministic win:** the gate ledger already parses a `duration=`
  marker key but 0/747 real markers carry it — emit it from
  `lib/gate_verifier_lib.sh` (`run_command_gate`) so committed ledgers start
  carrying machine-gate wall-clock for free.
- **Historical backfill:** the `.aitask-data` git log is a free
  second-resolution step-boundary trail (commit messages embed task id, step
  identity, and agent/model, e.g. "ait: Start work on tN", "ait: Record
  <gate> gate for tN", "ait: Archive completed tN") — usable to seed drift
  baselines for months that predate the instrumentation.

## Key reference points

- Step/substep → helper-call map produced during exploration (see plan):
  rendered `task-workflow-fast-/SKILL.md` step boundaries with file:line
  anchors; stamp-free spans enumerated above.
- Existing timestamp side effects: `aitask_update.sh` `updated_at` (minute
  granularity — too coarse), gate ledger `run=` (UTC seconds — best existing
  clock, start-only), `aitask_lock.sh` `locked_at`.
- Existing aggregate stores: `models_<agent>.json`
  `verifiedstats`/`usagestats` (agent/model × skill rolling buckets, written
  by `aitask_usage_update.sh`/`aitask_verified_update.sh` via
  `lib/verified_update_lib.sh`) — extend/reference, don't duplicate.
- Reporting surfaces to extend: `ait stats` (`aitask_stats.py` +
  `lib/stats_data.py`, which already derives 2 phase spans from the gate
  ledger: plan_approved→review_approved→merge_approved) and the stats TUI
  (`ait stats-tui`, panes under `.aitask-scripts/stats/panes/`, including
  `pipeline.py`).
- Profile name is a render-time constant in rendered skills
  (`{{ profile.name }}`) and available as `active_profile_filename` context
  var; agent string via `AITASK_AGENT_STRING` env or
  model-self-detection — but null before Step 7 on the fresh-plan path, so
  early stamps need a fallback.

## Scope notes

- This is a **parent task to be decomposed at planning time** — expected
  children along the lines of: (1) event-log schema + stamp helper +
  instrumented helpers, (2) skill-text stamps for the gap spans (+ goldens
  regeneration), (3) gate `duration=` emission, (4) report command with
  week-over-week / month-over-month drift, (5) transcript-enrichment layer +
  skillrun launch record, (6) historical backfill from the data-branch git
  log.
- Robustness contract: stats capture must be best-effort and non-blocking
  (never fail a workflow step), tolerate missing events (partial timelines
  from aborted/crashed runs are valid data), and tolerate skill-text stamps
  being skipped by an agent.
- Blind spots to document, not solve: Claude Code Web lane (no local
  transcript), Antigravity CLI (no known session store), Codex mid-session
  model switches.
