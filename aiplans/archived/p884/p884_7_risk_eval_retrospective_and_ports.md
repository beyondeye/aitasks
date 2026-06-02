---
Task: t884_7_risk_eval_retrospective_and_ports.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_7_risk_eval_retrospective_and_ports
Branch: aitask/t884_7_risk_eval_retrospective_and_ports
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-02 12:45
---

# Plan: t884_7 — Retrospective + deferred follow-ups

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Runs LAST (depends on all prior t884 children). Creates tasks only — no feature code.

## Context

Trailing retrospective child of t884 (task risk-evaluation feature). Per
`aidocs/planning_conventions.md`, this child documents outcomes and files the
standalone follow-ups t884 deliberately deferred, so nothing is silently lost.

**Verify-mode finding (2026-06-02):** the original plan listed three follow-ups.
Re-checking each against the current codebase, **follow-up #1 (cross-agent skill
ports) is unwarranted and is dropped** (user-confirmed). #2 and #3 stand.

## Steps

### 1. Retrospective note
Append a short retrospective to this plan's **Final Implementation Notes** (Step 8):
- **What shipped:** two-field risk plumbing (`risk_code_health` /
  `risk_goal_achievement`, t884_9 replacing t884_1's aggregate), `risk_evaluation`
  profile key (t884_2), risk-evaluation planning step + `## Risk` section + Step 7
  write (t884_3), risk-mitigation before/after procedure (t884_4), force-reverify
  read-time signal (t884_5), website docs (t884_6).
- **Did the design shapes hold up?** The read-time force-reverify signal
  (`aitask_risk_mitigation_landed.sh` → `--force-verify`) and the propose-confirm
  mitigation shape (mirroring `manual-verification-followup.md`) both shipped as
  designed; the gates seam was kept as a doc note, not code coupling.
- **Why #1 was dropped:** Claude is the single source of truth
  (`SOURCE_AGENT_ROOT = ".claude/skills"` in `lib/skill_template.py`); Codex
  (`.agents/skills/…-codex-/`) and OpenCode (`.opencode/skills/…`) closure
  variants **auto-render** from the Claude sources via `aitask_skill_render.sh`.
  The t884 risk closures (`risk-evaluation.md`, `risk-mitigation-followup.md`,
  `planning.md`, `SKILL.md`, `profiles.md`) carry **no** agent-specific
  (`{% if agent %}`) content, and t884 added no agent-specific stubs or
  `.codex/`/`.opencode/commands/` config. So the closure content already reaches
  every agent automatically — a manual port task would be a no-op. (Records the
  deviation from CLAUDE.md's general "suggest port tasks" guidance, which targets
  agent-specific surfaces, not auto-rendered shared closures.)

### 2. File the enum single-source refactor task (follow-up #2 — VALID)
Per the parent plan's "name the refactor, don't bury it" decision. Extract the
`high|medium|low` enum (shared by `priority` + the two risk fields) into a single
source. **Scope is larger than the parent plan's "~5 bash sites + board.py"
estimate** — `high|medium|low` is hardcoded across ~15 files (bash:
`aitask_create.sh`, `aitask_update.sh`, `aitask_ls.sh`, `aitask_archive.sh`,
`aitask_issue_import.sh`, `aitask_pr_import.sh`, `aitask_verification_followup.sh`,
`aitask_create_manual_verification.sh`; Python: `board/aitask_board.py`,
`settings/settings_app.py`, `brainstorm/brainstorm_app.py`, several `monitor/*`,
`agentcrew/agentcrew_dashboard.py`). File via `aitask_create.sh --batch --commit`:
- `issue_type: refactor`, `priority: low`, `effort: medium`
- labels: sensible existing ones (e.g. `refactor` / code-health-ish)
- description references t884, names the ~15 sites, proposes a bash sourced lib +
  mirrored Python constant (or a metadata file) as the single source.

### 3. File the gates-integration task (follow-up #3 — VALID)
Per the parent plan's "standalone-now + seam" decision. `t635_gates_framework.md`
exists (not yet done); `aidocs/gates/risk-evaluation-gate-seam.md` already
documents the integration design. File via `aitask_create.sh --batch --commit`:
- `issue_type: enhancement`, `priority: low`, `effort: medium`
- `depends: [635]` (or reference t635 in the body if a hard dep is too strong)
- labels: `task_workflow` + gates-ish
- description: wrap risk evaluation as a first-class `aitask-gate-risk` once gates
  land, replacing the forward-compat seam note; cross-reference t884 and the seam
  aidoc.

Use the **Batch Task Creation Procedure** (`task-creation-batch.md`) for both.

## Verification

- `ait ls` (or `aitask_query_files.sh resolve <id>`) shows each new follow-up with
  correct metadata and a t884 cross-reference.
- The retrospective note is committed in the consolidated plan.
- Confirm **no** cross-agent port task was filed (follow-up #1 dropped).

## Risk

### Code-health risk: low
- None identified. The task touches no source code — it files two follow-up tasks via `aitask_create.sh --batch` and writes a retrospective note in this plan. Zero blast radius on existing code.

### Goal-achievement risk: low
- None identified. The goal (document outcomes + file the deferred follow-ups) is fully covered: the verify pass already settled scope (dropped #1, confirmed #2/#3), and task creation uses a well-understood batch path.

## Post-Implementation

Standard Step 9 (child archival/merge per profile). This child files only
follow-ups — no feature code, so build/test verification is N/A.

## Final Implementation Notes

- **Actual work done:** Filed the two standalone follow-ups t884 deferred and
  recorded the retrospective. No source code touched.
  - **t911** — `extract_priority_risk_enum_single_source` (refactor, low/medium,
    labels `bash_scripts,python`): extract the `high|medium|low` enum to a single
    source.
  - **t912** — `risk_evaluation_gate_integration` (enhancement, low/medium,
    `depends: [635]`, labels `gates,task_workflow`): wrap risk evaluation as
    `aitask-gate-risk` once the gates framework lands.

- **Retrospective — what shipped (t884):** two-field risk plumbing
  (`risk_code_health` / `risk_goal_achievement`, t884_9 replacing t884_1's
  aggregate `risk`), the `risk_evaluation` profile key (t884_2), the
  risk-evaluation planning step + `## Risk` plan section + Step 7 frontmatter
  write (t884_3), the before/after risk-mitigation procedure (t884_4), the
  force-reverify read-time signal (t884_5), and website docs (t884_6). The two
  design shapes the user flagged — the read-time force-reverify signal
  (`aitask_risk_mitigation_landed.sh` → `--force-verify`) and the propose-confirm
  mitigation flow (mirroring `manual-verification-followup.md`) — both shipped as
  designed. The gates coupling was deliberately kept as a doc seam
  (`aidocs/gates/risk-evaluation-gate-seam.md`), not code, deferred to t912.

- **Deviations from plan:** The original plan listed **three** follow-ups. The
  verify-mode pass (this pick) found follow-up #1 (cross-agent skill ports to
  Codex/OpenCode) **unwarranted** and dropped it (user-confirmed). Rationale:
  Claude is the single source of truth (`SOURCE_AGENT_ROOT = ".claude/skills"` in
  `.aitask-scripts/lib/skill_template.py`); the Codex (`.agents/skills/…-codex-/`)
  and OpenCode (`.opencode/skills/…`) closure variants **auto-render** from the
  Claude sources via `aitask_skill_render.sh`. The t884 risk closures carry no
  agent-specific (`{% if agent %}`) content and t884 added no agent-specific
  stubs or `.codex/` / `.opencode/commands/` config, so the closure content
  already reaches every agent automatically. CLAUDE.md's general "suggest port
  tasks" guidance targets agent-specific surfaces, not auto-rendered shared
  closures. Also, the enum-refactor scope (t911) is larger than the parent plan's
  "~5 bash sites + board.py" estimate — ~15 files across bash + Python.

- **Issues encountered:** None. The working tree carried unrelated, pre-existing
  `brainstorm_*` / test edits and concurrent-writer changes on the aitask-data
  branch (`p756_4`, `codeagent_config.json`, `t909`); these were left untouched —
  only this task's own paths were staged.

- **Key decisions:** Drop follow-up #1 rather than file a no-op or verify-only
  task; keep t912's hard `depends: [635]` since the integration genuinely cannot
  start before the gates framework lands.

- **Upstream defects identified:** None

- **Notes for sibling tasks:** t884_7 is the last t884 child; once it archives the
  parent t884 archives too. The deferred work now lives in t911 and t912, both
  cross-referencing t884.
