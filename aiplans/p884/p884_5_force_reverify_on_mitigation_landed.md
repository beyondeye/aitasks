---
Task: t884_5_force_reverify_on_mitigation_landed.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_5_force_reverify_on_mitigation_landed
Branch: aitask/t884_5_force_reverify_on_mitigation_landed
Base branch: main
---

# Plan: t884_5 — Force-reverify when a "before" mitigation lands

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Depends on t884_1 (`risk_mitigation_tasks`) and t884_4 (populates it).

## Goal

Read-time signal at pick: if any listed `risk_mitigation_tasks` was archived
(its `completed_at`) **after** the plan's last `plan_verified` timestamp, force
the plan into VERIFY mode on the next pick. **No-op when the field is absent.**

## Steps

1. **`aitask_plan_verified.sh`** — add `--force-verify` to `decide`. **Byte-stable when omitted** (identical 8 `KEY:value` lines as today → existing parser untouched). With the flag: short-circuit to `DECISION:VERIFY` + distinct `DISPLAY:`.
2. **`planning.md` Step 6.0a** (SUFFIX, before existing §6.0 preference logic; do NOT renumber 6.0): read `risk_mitigation_tasks`; for each, locate its archived file, read `completed_at`; compare vs plan's most-recent `plan_verified` (`aitask_plan_verified.sh read`). If any later → pass `--force-verify` on the `decide` call. Empty/absent field → fall straight through to existing 6.0.
3. **Regenerate** variants + goldens; run `aitask_skill_verify.sh` — same commit.
4. Prefer extending `aitask_plan_verified.sh` (already allowlisted → no 7-touchpoint task). Only add a new helper if unavoidable, then apply the full allowlist.

## Reference patterns

- `aitask_plan_verified.sh` `cmd_decide` (~186-246) + `read` (~56-95) + `parse_ts` (~45-52).
- `aitask_archive.sh:145-147` — `completed_at` format. `aitask_query_files.sh` — archived-file resolution.

## Verification

- Unit: `decide <plan> 1 24` output identical pre/post change (empty diff); `... --force-verify` ⇒ `DECISION:VERIFY`.
- Simulate: mitigation `completed_at` later than last verification ⇒ forces verify; earlier ⇒ normal; field absent ⇒ unchanged.
- `aitask_skill_verify.sh` passes; `shellcheck aitask_plan_verified.sh`.

## Notes for sibling tasks

Invisible plumbing — t884_6 docs it as one line. Keep the 8-line decide contract + 6.0 numbering stable.
