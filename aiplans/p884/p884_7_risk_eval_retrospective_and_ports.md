---
Task: t884_7_risk_eval_retrospective_and_ports.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_7_risk_eval_retrospective_and_ports
Branch: aitask/t884_7_risk_eval_retrospective_and_ports
Base branch: main
---

# Plan: t884_7 — Retrospective + deferred follow-ups

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Runs LAST (depends on all prior t884 children).

## Goal

Document outcomes and file the standalone follow-ups t884 deliberately deferred,
so nothing is silently lost. Creates tasks only — no feature code.

## Steps

1. **Retrospective note** — short write-up (in this plan / `aiplans/`): what shipped, deviations, whether the read-time signal + propose-confirm shapes held up.
2. **File cross-agent skill-port tasks** (CLAUDE.md: Claude-first, then suggest separate aitasks): port the t884 skill/closure changes (`risk-evaluation.md`, `risk-mitigation-followup.md`, planning.md §6.1/6.0a, SKILL.md Step 7/8d, profiles.md key) to **Codex** (`.agents/skills/`, `.codex/`) and **OpenCode** (`.opencode/`). One task each (or one combined) via `aitask_create.sh --batch --commit`.
3. **File enum single-source refactor task** — extract `priority`+`risk` `high|medium|low` (hardcoded across ~5 bash sites + board.py) to a single source.
4. **File gates-integration task** — wrap risk evaluation as `aitask-gate-risk` once t635 lands (reference t635, replaces the seam note in t884_3).

Reference each new task back to t884; set sensible priority/effort/labels.

## Reference patterns

- `task-creation-batch.md`; `aidocs/adding_a_new_codeagent.md`; `aidocs/gates/aitask-gate-framework.md`.

## Verification

- `ait ls` shows each follow-up with correct metadata + t884 cross-reference; retrospective note committed.

## Notes for sibling tasks

This is the single surfacing point for the deferred ports/refactor/gates work.
