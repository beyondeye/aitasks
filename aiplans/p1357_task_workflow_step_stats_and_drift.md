---
Task: t1357_task_workflow_step_stats_and_drift.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t1357 — Per-step execution stats and drift reporting for task-workflow

---
Task: t1357_task_workflow_step_stats_and_drift.md
Worktree: (none — current branch)
Branch: main
Base branch: main
Output branch: main
---

## Context

aitask-pick + task-workflow are the development critical path; today nothing
measures where their time goes. Timing, agent/model, and outcome are never
joined: the gate ledger has start-only `run=` stamps (its `duration=` key is
parsed but never emitted — 0/747 markers), `implemented_with` is one string per
task, and `models_*.json` holds undated counters. The goal is **per-step /
per-substep** execution statistics dimensioned by **code-agent × LLM model ×
reasoning effort**, with **week-over-week and month-over-month drift
reporting**, captured by **deterministic in-workflow instrumentation** (not
tmux capture), with agent-transcript mining as an enrichment layer only.

Decisions already confirmed with the user during exploration/planning:

- Unit of analysis = step/substep timings (not per-run totals).
- Storage = append-only event log: local git-ignored spool during the run,
  flushed at end-of-run into **one per-run JSONL** committed on the task-data
  branch — conflict-free under concurrent sessions, one commit per run,
  crashed runs leave a spool the next capture sweeps in.
- Reasoning effort is a **new dimension** (nothing records it today; only
  Claude Code transcripts contain it — Codex/OpenCode must be stamped
  explicitly or recorded `unknown`).
- Transcript enrichment: **Claude Code first**; Codex/OpenCode as an explicit
  follow-up task. Stats-TUI drift pane: explicit follow-up task. Both
  follow-ups are created at decomposition time (not vague deferrals).
- This is a **decomposed parent**: 7 sibling children + 2 follow-up top-level
  tasks, created post-approval.

## Architecture

### Event schema (JSONL, one object per line, `v: 1`)

```json
{"v":1,"ts":"2026-07-31T12:34:56Z","task":"1357","run":"r1753963200_41623",
 "step":"planning","sub":"risk_evaluation","ev":"begin",
 "skill":"pick","profile":"fast","agent":"claudecode/opus5","effort":"high",
 "src":"skill","extra":{"gate":"plan_approved","attempt":1}}
```

- `ev`: `begin` | `end` | `point` (single-instant events, e.g. gate recorded,
  claim, archive). Durations are derived at report time from begin/end pairs
  or consecutive points; missing ends are tolerated (partial timelines from
  aborted runs are valid data).
- `step` vocabulary (fixed list, documented in the lib): `pick_select`,
  `claim`, `env_setup`, `planning` (subs: `plan_mode`, `risk_evaluation`,
  `externalize`), `implement`, `review` (sub: `iteration`), `commit`,
  `gates`, `merge`, `archive`, `feedback`, `run` (run_begin/run_end).
- Dimensions (`skill`, `profile`, `agent`, `effort`) are **not** trusted from
  individual stamps: a per-run **manifest** is the single source; the capture
  step back-fills dims onto every event at flush time (derived-state
  single-source rule). `effort` defaults to `unknown`.
- `src`: which surface stamped it (`helper:<script>` | `skill` | `capture` |
  `backfill`) — provenance for later quality analysis.

### Runtime layout (git-ignored, repo-root `.aitask-stats/`)

```
.aitask-stats/
  runs/t<id>/manifest.yaml    # run_id, task, skill, profile, agent, effort, started_at
  runs/t<id>/events.jsonl     # spool — appended by stamps, O_APPEND single write
  launches/…                  # (child 5) skillrun launch records
```

### Committed layout (task-data branch)

```
aitasks/metadata/stats/events/<YYYY-MM>/t<id>_<run_id>.jsonl
```

One file per run → no merge conflicts by construction. Reports glob monthly
dirs. Written+committed only by the capture verb via `./ait git`.

### New helper: `.aitask-scripts/aitask_stats_step.sh` (+ `lib/stats_step_lib.sh`)

Verbs (all **fail-safe**: internal `set -euo pipefail` but every verb's body
runs under a trap that reports to stderr and exits 0 — a stats failure must
never break the workflow; call sites additionally use `|| true`):

- `begin-run <task_id> --skill <s> [--profile <p>]` — mints
  `run_id=r<epoch>_<pid>`, writes the manifest, stamps `run/begin`. Idempotent
  per task (existing manifest for a live run is reused; a stale manifest from
  a dead run is swept into an orphan capture first).
- `stamp <task_id> <step> <begin|end|point> [--sub <s>] [k=v …]` — appends one
  line to the spool. No manifest → auto `begin-run` with `skill=unknown`.
- `set-dim <task_id> [--agent <a/m>] [--effort <e>]` — updates the manifest
  (called from agent-attribution / self-detection sites).
- `capture <task_id> [--outcome done|aborted|deferred]` — stamps `run/end`,
  merges manifest dims into every spool line, writes the per-run file under
  the data branch, `./ait git add/commit` (path-scoped, best-effort like
  `aitask_gate_record.sh`), removes the spool. `--sweep-orphans` also
  captures any stale manifests (dead pid) it finds, with `outcome=orphaned`.

## Child decomposition (created post-approval)

Sequential sibling deps (default). Each child gets a self-contained task file
+ plan per Child Task Documentation Requirements.

**t1357_1 — Event schema, stamp/spool helper, capture verb, tests.**
`aitask_stats_step.sh` + `lib/stats_step_lib.sh` as specified above; `.gitignore`
+ `aitask_setup.sh` gitignore-block entries for `.aitask-stats/` (read
`aidocs/framework/aitasks_extension_points.md` + `shell_conventions.md` first);
`ait` dispatcher entry (`ait stats-step …`) for manual stamping/debugging.
Bash tests: schema shape, fail-safe contract (helper exits 0 when spool dir is
unwritable — negative control proves the trap path), orphan sweep, capture
commit path against a scratch repo. Riskiest-spike-first: this child proves
the schema + concurrency contract before anything depends on it.

**t1357_2 — Instrument the deterministic helpers + emit gate `duration=`.**
Add guarded stamp calls (`aitask_stats_step.sh … || true`) to:
`aitask_pick_own.sh` (begin-run + `claim` point at OWNED),
`aitask_gate_record.sh` (`gates` point with `gate=<name>`),
`aitask_plan_externalize.sh` (`planning/externalize` point),
`aitask_archive.sh` (`archive` point),
`aitask_usage_update.sh` (`feedback` point — also the deterministic capture
backstop: triggers `capture` if a manifest is still open),
`aitask_update.sh --status` transitions (point). Plus: time the verifier in
`lib/gate_verifier_lib.sh:run_command_gate` and pass `duration=<N>s` through
the existing `aitask_gate.sh append` slot (parser already supports it), and
stamp wall time in `gate_orchestrator.py`'s reconcile path. Tests: each
instrumented helper still passes its existing test file; new asserts that a
stamp appears in the spool; negctrl that a broken stats lib does not fail the
helper.

**t1357_3 — Skill-text stamps for gap spans + end-of-run capture hook.**
Edit the Jinja sources under `.claude/skills/task-workflow/` (SKILL.md,
`planning.md`, procedure files): stamps for implement begin/end (Step 7 body,
WF:364), review-loop iterations (Step 8 loop), risk-evaluation begin/end,
EnterPlanMode/ExitPlanMode span, env-setup under no-worktree profiles, and
the **capture call in Step 9b** next to satisfaction-feedback (plus capture
`--outcome aborted` in `task-abort.md` / `lock-release` path). Extend
`model-self-detection.md` to also return reasoning effort where
self-detectable (Claude Code; else `unknown`) and call `set-dim`. Rerender all
profiles + regenerate goldens in the same commit
(`aitask_skill_verify.sh`; read `skill_authoring_conventions.md` first).
Suggest separate aitasks for the Codex/OpenCode skill trees per CLAUDE.md.

**t1357_4 — Reporting: step timings + WoW/MoM drift in `ait stats`.**
New `lib/stats_step_data.py` (loader: glob monthly event dirs, pair
begin/end, build per-(step, sub, agent, model, effort, profile) duration
samples bucketed by ISO week and calendar month; one validated reader).
Extend `aitask_stats.py`: "Step timings" section (median/mean/N per step ×
dims) and "Drift" section — per step, median vs previous week and previous
month with % change, flagged when |Δ|>threshold (default 20%) AND both
periods have ≥ min samples (default 3); thresholds in `stats_config.json`.
New CSV export mode for step events. Python tests via the suite runner
(fixture event files; read only the last verdict line; beware the `-k`
filter pitfall). Update `aitask-stats` SKILL.md (already stale — refresh the
section list while touching it).

**t1357_5 — Skillrun launch record + Claude Code transcript enrichment.**
`aitask_skillrun.sh` / `aitask_codeagent.sh` emit a launch record (ts, agent
string, skill, profile, pid, cwd) to `.aitask-stats/launches/`; where
obtainable, the capture step records the Claude Code session id (newest
`~/.claude/projects/<mangled-cwd>/*.jsonl` matching the run window + pid
heuristic, recorded with provenance so a bad join is discardable). A
transcript slicer (python, machine-local, never committed raw) sums tokens /
tool-calls / `effort` per step window and writes an enrichment sidecar next
to the per-run event file (`…_enrich.jsonl`, committed). Report shows token
columns when enrichment exists. Codex/OpenCode formats documented in
`aidocs/framework/` (from the exploration survey) for the follow-up task.

**t1357_6 — Historical backfill from the data-branch git log.**
One-shot(able) `aitask_stats_backfill.sh`: parse `./ait git log` on the data
branch (`ait: Start work on tN`, `ait: Record <gate> gate for tN`,
`ait: Archive completed tN`, usage/verified messages carrying
`<agent>/<model>`) into synthetic coarse events (`src=backfill`,
`effort=unknown`) written into the same monthly layout, guarded against
double-backfill (marker file). Gives drift baselines for months predating
the instrumentation.

**t1357_7 — Retrospective evaluation (trailing child, depends on all).**
After ≥2–3 weeks of accumulated data: assess event completeness (which
skill-text stamps actually fire — the `src` field discriminates), tune drift
thresholds, decide whether enrichment join quality is good enough, review the
deferred follow-ups' priority, and file further follow-ups only if data
justifies them.

### Follow-up top-level tasks (created at decomposition, `depends: [1357]`, `--followup-of 1357`)

- **stats-TUI drift pane** — plotext chart of step medians over time in
  `ait stats-tui` (new pane under `.aitask-scripts/stats/panes/`).
- **Codex + OpenCode transcript enrichment** — port the t1357_5 slicer to
  Codex rollouts (`duration_ms`, `reasoning_output_tokens`) and OpenCode
  storage (USD `cost`), formats already surveyed and documented.

## Explicitly out of scope (dispositions)

- Claude Code Web lane (no local transcript) and Antigravity CLI (no known
  session store): documented blind spots — deterministic backbone still
  works there; enrichment is absent. Documented in t1357_5's aidocs page.
- tmux/shadow capture as a stats source: rejected (lossy, unstructured).
- Extending `verifiedstats` rolling buckets for step data: rejected as
  primary store (1 month of history is too shallow for drift); the event log
  is the source of truth.

## Verification

- Per-child bash/python tests as listed above (each child owns its tests).
- End-to-end: after t1357_3 lands, run one real `/aitask-pick` cycle on a
  scratch task and verify (a) spool fills during the run, (b) Step 9b capture
  commits exactly one `aitasks/metadata/stats/events/<month>/t<id>_r*.jsonl`
  on the data branch, (c) `ait stats` (after t1357_4) renders the step table
  from it, (d) killing a session mid-run leaves a spool that the next run's
  sweep captures with `outcome=orphaned`.
- Drift math: fixture with two synthetic months where one step's median
  doubles → drift section flags exactly that step (and a negative control
  where nothing changed → no flags).

## Step 9 reference

Post-implementation (per child): commit via Step 8, merge/archive via Step 9
of task-workflow; parent archives after all children complete. The parent
task itself ends this session at the child checkpoint after children + plans
are created (parent reverts to Ready, lock released).

## Risk

### Code-health risk: medium
- Stamp calls land in load-bearing critical-path helpers (`aitask_pick_own.sh`, `aitask_gate_record.sh`, `aitask_archive.sh`) — a defect could break claiming/archival for every user · severity: medium · → mitigation: fail-safe exit-0 trap contract + `|| true` at every call site + negative-control tests in t1357_1/t1357_2 (in-plan, no separate task)
- Skill-text changes cascade across per-profile renders and goldens (agent-invariance surface) · severity: medium · → mitigation: t1357_3 regenerates goldens in the same commit and runs `aitask_skill_verify.sh` (in-plan)
- New persistent surfaces (`.aitask-stats/`, `aitasks/metadata/stats/`) add framework state to maintain · severity: low · → mitigation: single writer (capture verb), one validated reader (t1357_4 loader), schema `v` field for evolution (in-plan)

### Goal-achievement risk: medium
- Skill-text stamps are best-effort (an agent can skip a prose instruction), so substep coverage may be spotty, undermining per-substep stats · severity: medium · → mitigation: deterministic helper stamps carry the primary spans; `src` provenance lets t1357_7 measure which skill stamps actually fire and harden only the ones that matter (in-plan)
- Reasoning-effort dimension may stay `unknown` for most rows (only Claude Code exposes it today) · severity: medium · → mitigation: t1357_5 recovers it from Claude Code transcripts; Codex/OpenCode follow-up task created now (in-plan)
- Drift detection needs enough samples per (step × dims) cell; early weeks will be sparse · severity: low · → mitigation: min-sample floor in the drift rule + t1357_6 backfill for coarse baselines (in-plan)

No standalone before/after mitigation tasks proposed — every mitigation above
is covered by an in-plan child; the trailing retrospective child (t1357_7) is
the "after" check (created at decomposition, since a decomposed parent skips
Step 8d).
