---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: high
depends: []
issue_type: test
status: Implementing
labels: [shadow, skills, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2179
implemented_with: claudecode/opus5_5
created_at: 2026-11-03 08:34
updated_at: 2026-11-03 09:55
---

## Context

Child 1 of t2179 (shadow `>q` definition experiments). Repeated `>q` answers from the
aitask-shadow companion (observed while shadowing aitasks_go t60_2) jumped straight
to a recommendation with little explanation of the decision or of the options'
trade-offs, although the skill already asks for that. t2179 measures empirically
whether a concise intent-based definition suffices or whether more explicit wording
improves consistency, across the real Codex and Claude Code default agents.

User decisions (t2179 planning, 2026-11-02):
- **Budget: pilot only, then ask.** This child builds the harness and runs ONLY the
  bounded pilot. No main-matrix spend here; t2179_2 starts with an explicit user
  approval gate on the measured numbers.
- Two children: this one (harness, frozen variants/fixtures, rubric, pilot, freeze
  point) and t2179_2 (main matrix, blinded scoring + audit, report).
- The production `>q` definition is NOT changed. Variants live only in the
  experiment directory.

The full design (variant wording, sandbox layout, trace validator, outcome classes,
limits, tests) is in `aiplans/p2179/p2179_1_shadow_q_harness_and_pilot.md` and the
parent plan `aiplans/p2179_shadow_q_definition_experiments.md`. Read both.

## Key Files to Create

All under the new directory `aidocs/benchmarks/shadow_q/` (code branch):
- `freeze.py`: pin the repo SHA and the sha256 of `.claude/skills/aitask-shadow/SKILL.md.j2`,
  both agents' fast render trees and both stubs; extract the `>q` bullet verbatim
  (occurs exactly once).
- `variants/v1_baseline.md` … `v4_prescriptive.md` + `variants/README.md` (hypotheses).
- `fixtures/<scenario>/` (file_selection, runnable_examples, go_versions,
  working_wait) + `fixtures/PROVENANCE.md` + frozen aitasks_go `CLAUDE.md`/`AGENTS.md`.
- `harness.py` (sandbox build, replay stubs, launch, limits, metadata),
  `validate.py` (trace → outcome class), `judge.py` (blinded, both agents' judges,
  calibration controls), `rubric.md`, `judge_prompt.md`, `limits.json`,
  `matrix.json` (proposed main matrix), `pilot_report.md`, `runs/pilot/…`.
- `tests/test_shadow_q_harness.py`: offline, fake `claude`/`codex` on PATH.

## Reference Files for Patterns

- `.claude/skills/aitask-shadow/SKILL.md.j2`: the `>q` bullet (~lines 281-300 at 42b547c67).
- `.claude/skills/aitask-shadow/SKILL.md` (Claude stub, `--agent claude`, dispatches to
  `.claude/skills/aitask-shadow-fast-/SKILL.md`) and `.agents/skills/aitask-shadow/SKILL.md`
  (Codex stub, `--agent codex`, dispatches to `.agents/skills/aitask-shadow-fast-codex-/SKILL.md`).
  Five procedure files differ between the two renders.
- `.aitask-scripts/aitask_codeagent.sh resolve shadow` / `--dry-run invoke shadow`;
  `lib/agent_string.sh` (`DEFAULT_AGENT_STRING`); `lib/agent_launch_utils.py`
  `resolve_dry_run_command`; `monitor/minimonitor_app.py` `action_launch_shadow`.
- `aidocs/framework/shell_conventions.md` ~259-266 (`claude -p` caveat: explicit opt-in here).
- Prior-art research layout: `aidocs/testing_engine/t1954_parser_research/`.
- Source facts: aitasks_go (`ait projects resolve aitasks_go`)
  `aitasks/t60/t60_2_m3_2g_go_test_adapter.md` at aitasks_go `b523a6bc`.

## Implementation Plan

Follow `aiplans/p2179/p2179_1_shadow_q_harness_and_pilot.md` steps 1-9.

## Verification Steps

- `python3 tests/test_shadow_q_harness.py` passes; the occurs-once mutant goes red.
- `bash tests/run_all_python_tests.sh --test-dir <dir>` is green for the new module.
- The pilot JSONL accounts for all 12 sessions / 16 `>q` answers, each with exactly
  one outcome class and a CLI-reported model. At least one `valid` trial per agent.
  Invocations ≤ 80. Thresholds are stop-launch, with any overrun reported.
- Judge calibration controls are ordered correctly.
- `git diff --stat` shows nothing under `.claude/skills/` or `.agents/`.
- End by presenting `pilot_report.md` numbers to the user. Do not start the main run.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-03T07:55:28Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-03T15:02:08Z status=pass attempt=1 type=human
