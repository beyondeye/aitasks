---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [shadow, concurrency]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-04 16:28
updated_at: 2026-10-05 15:05
---

## Origin

Risk-mitigation ("after") follow-up for t1877, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — extract() false positive (SKILL.md.j2 → SKILL.md) kept by admission/trail

(From t1877's risk evaluation.) Parallel admission and the trail gatherer keep `extract()`, including its measured false positive (`…/SKILL.md.j2` → `…/SKILL.md`, 32 references in 21 plans), which can manufacture an admission `CONFLICT`/trail overlap on the wrong file. · severity: medium

## Goal

`.aitask-scripts/lib/plan_paths.py` `_TOKEN` (`[A-Za-z0-9_./-]+\.(?:sh|py|md|yaml|yml|json|toml)`) has no right boundary, so a path with a longer, multi-part extension is truncated to a DIFFERENT, often tracked, file: `.claude/skills/aitask-pick/SKILL.md.j2` extracts as `.claude/skills/aitask-pick/SKILL.md` (the rendered stub). t1877 measured 32 such references in 21 archived plans (`aidocs/framework/plan_path_reference_extraction_findings.md` §7). The remote drift check no longer uses `extract()` since t1877; `lib/parallel_admission_collect.py` (`plan_extraction`) and `lib/trail_gather.py` (`_classify_plan_paths`) still do, so a plan that only edits a template can collide with whatever task touches the rendered stub.

- Make `extract()` reject a match that is immediately followed by a path character (e.g. a negative lookahead `(?![A-Za-z0-9_.-])` after the extension group), so `x/SKILL.md.j2` yields nothing rather than `x/SKILL.md`. Decide explicitly what `a.md.` (a sentence-final period) and `a.mdx` should yield, and pin both in `tests/test_plan_paths.py`.
- Keep `tests/test_plan_paths_seam.sh`'s single-grammar guard (b) passing (the change stays inside `plan_paths.py`), and keep the `test_remote_drift_check.sh` Test 14 golden consistent (it no longer exercises `extract()`, but its golden set documents the grammar).
- Measure before/after on the live corpus and record it in findings §7: `aitask_parallel_admission.sh replay --candidates auto` (RATES / CAUSE_RATE: CLEAR / CLEAR_CAVEATED / CONFLICT / UNCHECKABLE counts) and `sweep --source plan`, plus the trail gatherer's `corpus_status` (`no_extractable_paths` / `partial_extractable`) counts. A verdict moving from CONFLICT to CLEAR must be traceable to a removed `.md.j2`-style token, and any plan whose surface becomes empty (`no_extractable_paths`) must be listed.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-05T12:05:22Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-05T13:24:19Z status=pass attempt=1 type=human
