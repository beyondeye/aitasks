---
Task: t986_2_phase_autodetection_module.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_1_*.md, aitasks/t986/t986_3_*.md, aitasks/t986/t986_4_*.md, aitasks/t986/t986_5_*.md, aitasks/t986/t986_6_*.md
Archived Sibling Plans: aiplans/archived/p986/p986_*_*.md
Worktree: aiwork/t986_2_phase_autodetection_module
Branch: aitask/t986_2_phase_autodetection_module
Base branch: main
---

# Plan: t986_2 — Phase-autodetection module (ledger-first, text fallback)

## Context

The shadow needs to know which workflow phase the shadowed agent is in. Decision:
ledger-first, text fallback. Pure headless module; parallelizable with t986_1.
**Coordinate with t635_8** (shared TUI gate-ledger parser) — import, do not fork.

## Implementation steps

1. **Create** `.aitask-scripts/monitor/phase_detect.py` (no Textual import).
   Public: `detect_phase(task_file, captured_text) -> phase` + phase constants.
2. **Ledger-first:** import `derive_status` / `parse_gate_runs` from
   `lib/gate_ledger.py`; read the source task file's `## Gate Runs`; map passed
   gates → phase (no gates → planning; `plan_approved` → implementing;
   `risk_evaluated` informs planning/impl; `review_approved` → review;
   `build_verified`/`merge_approved` → done/archived).
3. **Text fallback:** when ledger is absent/insufficient or no task file resolves,
   scan `captured_text` for markers — "Implementation complete. Please review…"
   (Step 8), "Proceed with merge…" (Step 9), branch-base prompt (Step 5) — and
   the AskUserQuestion shape (reuse/extend `monitor/prompt_patterns.py`).
4. **Precedence:** live on-screen AskUserQuestion > ledger > text-history.

## Verification

- Task-file fixtures at various gate states map to the expected phase (ledger path).
- Transcript fixtures (review prompt, merge prompt, AskUserQuestion, plain planning) map to the expected phase (text path).
- A live AskUserQuestion overrides the ledger-derived phase (precedence).
- The module imports gate-ledger parsing from `lib/gate_ledger.py` (no forked copy).

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
