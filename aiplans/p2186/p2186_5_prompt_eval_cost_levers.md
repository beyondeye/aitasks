---
Task: t2186_5_prompt_eval_cost_levers.md
Parent Task: aitasks/t2186_generic_agent_prompt_eval_harness.md
Sibling Tasks: aitasks/t2186/t2186_1_*.md, aitasks/t2186/t2186_2_*.md, aitasks/t2186/t2186_3_*.md, aitasks/t2186/t2186_4_*.md, aitasks/t2186/t2186_6_*.md, aitasks/t2186/t2186_7_*.md
Archived Sibling Plans: aiplans/archived/p2186/p2186_*_*.md
Base branch: main
Output branch: main
---

# t2186_5: Cost levers as opt-in modes: cache-grouped judging, sequential stopping, single judge plus audit

Child 5 of t2186. The parent plan is `aiplans/p2186_generic_agent_prompt_eval_harness.md`; the task file carries the shared
constraints, the facts established during exploration and the target layout. Read both. Treat any deviation recorded in an archived sibling plan's Final Implementation Notes as authoritative over this plan.

## Context

Child 5 of t2186. It builds and measures three cost levers, each **opt-in, with the defaults
unchanged**: two judges throughout, fixed repetitions, and the original judge-prompt structure.
- **cache-grouped judging**, with a pre-registered v2 judge-prompt structure;
- **sequential sampling**, with pre-registered stopping rules on the conservative decision
  score;
- **single judge plus sampled audit.**

A small judge-cache probe is approval-gated; a declined probe is recorded as unmeasured. This
child recommends no new default. t2186_7's pre-registered investigations decide that.

### Pre-phase (risk mitigations)

1. [cli_flag_recheck] As the **first implementation step** of t2186_2 (adapters), t2186_3 (web
   flag) and t2186_5 (judge system-prompt arms): run `claude --help`, `codex exec --help` and
   `codex exec resume --help`; confirm that every flag the child's adapter code emits exists in
   the installed version; record `claude --version` and `codex --version` in the child plan; and
   add a test that pins the emitted argv for every agent × turn × option case. A missing or
   renamed flag **stops the child** and is reported to the user, never worked around silently.
   This step is copied verbatim into those three child task files.

## Implementation

### `prompt_eval_cost_levers` (small gated probe)

**Every lever ships as an opt-in mode. The defaults stay as they are:** two judges throughout,
fixed repetitions, the original (v1) judge-prompt structure. This child builds and measures; it
recommends no new default. Whether an alternative should become the default is decided by
t2186_7's pre-registered investigations, against evidence this child alone cannot provide.
Passing calibration controls is recorded as necessary, never as proof of equivalence.

1. **Cache-grouped judging** — answer judgings grouped by scenario (seeded order within a group),
   blind ids pre-assigned. A pre-registered judge-prompt v2 for Claude moves the shared context
   (rubric, reference, screen, task) into the system prompt (`--append-system-prompt-file`,
   flag verified) with the answer alone in the user message; same text bytes, so calibration
   controls are re-run under v2 before v2 scores anything. Codex keeps the v1 structure (the
   answer is already last) and only gains grouping. A second Claude arm,
   `--system-prompt-file` (replacing Claude Code's default system prompt), is offered in the
   same probe as a separate pre-registered option.
2. **Probe** (approval-gated, ≈ 4-6 Claude + 4-6 Codex judge calls on the pilot's controls):
   measure cost, `cache_read_input_tokens` / `cached_input_tokens`, and calibration under each
   arm against the pilot's $0.277 / 18k per call. Declined → recorded unmeasured. The probe keeps
   every per-call verdict (private) and its numbers (public, `DESIGN_LEDGER.md` lever data), so
   t2186_7 can reuse them as part of, never all of, its structure comparison.
3. **Sequential sampling** — `pecore/sequential.py`: a pre-registered rule in the spec
   (`sampling: {min_reps, max_reps, wave, rule: "wilson_decided", target, z}`, plus t2186_3's
   `min_coverage`), bound into the approval digest. `run` schedules reps in waves and decides per
   cell, **only on t2186_3's decision quantities, never on an exclusion-based rate**:
   - **stop as success** only when the decision score's Wilson lower bound ≥ target **and**
     coverage ≥ `min_coverage`;
   - **stop as failure** only when even the optimistic bound's Wilson upper bound < target;
   - otherwise continue to `max_reps`. A cell that ends below `min_coverage` is reported as
     "insufficient coverage", never as decided;
   - the target must be achievable: < 1, and reachable by an all-success cell at `max_reps`. The
     spec loader refuses otherwise.

   The effect is measured offline by seeded simulation: expected reps saved and the actual
   decision error rate across true rates, unresolved rates and look counts. No spend.
4. **Single judge + sampled audit** — `pecore/audit.py`: the primary judge scores every answer;
   the second judge scores a pre-registered audit sample (every borderline answer — any failure
   flag, or a `could_choose` mean within a margin of the threshold — plus a seeded fraction of the
   rest); controls for both. A first offline look against the pilot's two-judge `scores.json`
   (16 answers): agreement, missed disagreements and false passes against the two-judge verdict,
   Wilson intervals, labelled n = 16 and **not sufficient for a default**; projected savings for
   the shadow_q main matrix.
5. **Tests** (`tests/test_prompt_eval_cost.py`): grouping order and blind-id stability, v2
   prompt bytes = v1 bytes split at the declared boundary, recalibration before scoring, the
   stopping rule on synthetic streams, simulation determinism, audit-sample selection and the
   pilot-derived agreement numbers. **Exclusion regression:** a mostly incomplete cell is fed
   repeating waves of 1 complete answer + 9 `uncertain_report` answers. It never stops as a
   success at any wave up to `max_reps`, though its historical `compliance_rate` is 100%. A
   consistently complete cell at the same true rate stops as a success.

## Step 9

Archive via the normal Step 9 (Post-Implementation). The parent t2186 auto-archives with its last child.

## Verification

- Each lever is measured or recorded unmeasured in `DESIGN_LEDGER.md`; the simulation and
  pilot-calibration numbers are reproducible from committed inputs.
- The mostly incomplete cell never stops as a success.
- The defaults are unchanged (tested).
- The tests and `run_all_python_tests.sh --test-dir` are green; `check-public --staged` passes;
  `git diff --stat` is clean outside the allowed paths.
- The probe runs only after a recorded approval of its printed manifest.

## Risk

### Code-health risk: low
- Opt-in modes; the defaults unchanged. · severity: low · → mitigation: none (contained by
  design)

### Goal-achievement risk: medium
- The cache lever changes the judge's structure, so its scores are not directly comparable with
  the pilot's; and the probe may be declined. · severity: low · → mitigation: none (addressed in
  design: v2 pre-registered and recalibrated, no equivalence claim from controls, "unmeasured"
  allowed)
- Repeated looks inflate the error rate. · severity: low · → mitigation: none (addressed in
  design: a conservative z; the simulation reports the actual rate)
- CLI drift could drop or rename the system-prompt flags. · severity: low (residual — addressed
  by inline pre-phase cli_flag_recheck) · → mitigation: inline pre-phase cli_flag_recheck

### Planned mitigations
- timing: pre-phase | name: cli_flag_recheck | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: CLI drift silently dropping or renaming the judge system-prompt flags | desc: check every emitted flag against the installed `--help`, record both CLI versions, pin the emitted argv in a test; a missing flag stops the child and is reported
