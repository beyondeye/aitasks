---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [1420]
issue_type: feature
status: Implementing
labels: [shadow, monitor, codex, opencode]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/opus5
created_at: 2026-08-10 08:42
updated_at: 2026-08-13 21:30
---

Extend the advisory workflow-phase signal after t1420 so native Codex and OpenCode prompts have phase-aware detection comparable to Claude. Inventory real current prompt surfaces and stable version variants; add narrowly scoped, ordered patterns only where wording is distinctive; keep framework-authored task-workflow checkpoint phrases as the shared cross-agent baseline; retain UNKNOWN and graceful degradation when a native prompt is unrecognized; do not alter existing awaiting_input_kind semantics unless compatibility impact is documented and tested. Verify Codex and OpenCode planning/review/merge prompts are classified when observable, unrelated confirmations do not receive a workflow phase, and every detected or wrong phase remains advisory-only and cannot block any shadow capability.

## Coordination

- **Agent identity is the root blocker this task hit** (measured 2026-08-13).
  `pane_current_command` is not authoritative: `claude` and `opencode` are native
  binaries and report their own names, but a wrapper-style Codex install reports
  `node` because its launcher spawns the real binary as a direct child. Every
  per-agent table would have shipped wired-but-dormant for Codex. Resolved here
  with a two-rung ladder (`lib/agent_keys.agent_key_from_pane`: the pane command,
  then one level of children). The **durable** fix — an engine-owned
  `@aitask_agent` pane option stamped at launch, exact instead of inferred — is
  deliberately NOT in this task: it touches ~5 launch sites
  (`agent_command_screen`, `tui_switcher` ×3, `agentcrew_runner`,
  `history_screen`, `codebrowser_app`) and covers only framework-launched panes.
  Worth its own task.
- **The auto-recheck review loop was deliberately NOT unlocked.** Filling the
  per-agent tables makes `workflow_phase.live_tiers_available` true for Codex and
  OpenCode, which previously doubled as minimonitor's arming gate. Since that
  loop *injects* keystrokes into the shadow pane, the gate was split off into
  `review_loop.review_loop_agent_supported` / `REVIEW_LOOP_AGENTS` and stays
  Claude-only. Widening it needs its own live evidence per agent — a follow-up.
- **Tier B is empty for both agents by measurement.** Neither CLI has an
  `ExitPlanMode` analogue, so their only native dialogs are tool confirmations,
  which carry no workflow phase. Their phase comes from Tier A or the ledger.
  Do not "fill in" `NATIVE_KIND_PHASE` without a new measurement.
- **t1509** (shadow-readiness detectors for non-Claude shadows, `anchor: 1159`)
  — the **shadow** half of the same cross-agent gap this task closes for the
  **followed** half. It deliberately carries no `depends:` on this task, because
  a Codex-shadow-of-a-Claude-pane setup needs only its own detector. But it
  raises a safety question this task's work bears on: `shadow_prompt_ready`'s
  negative half consults `PROMPT_PATTERNS_BY_AGENT[agent]`, and `codex`
  currently has a single placeholder pattern while `opencode` has none — so a
  thin pattern list weakens the "no dialog is showing" exclusion that stops the
  loop injecting Enter into a shadow parked at a dialog. If the per-agent
  dialog patterns added here land first, t1509's negative half becomes reliable
  for free; coordinate rather than duplicating pattern work.

  **Landed first — what t1509 inherits.** `codex` now carries `codex_question`
  and `codex_permission` beside `codex_yes_proceed`, and `opencode` carries
  `opencode_question` and `opencode_permission` (previously it had none at all,
  so an OpenCode agent blocked on a permission dialog read as *idle*). That is
  the stronger exclusion t1509 wanted.

  **But t1509 must also fix the resolution, not only the detectors.** Its two
  shadow-side sites (`minimonitor_app.py:2468`, `:2554`) resolve from
  `shadow_command` via the one-rung `agent_key_from_command`, and there is no
  snapshot for a shadow pane to carry a resolved key. A Codex shadow reports
  `node`, so `SHADOW_READY_DETECTORS.get("")` misses for it regardless of which
  detectors exist. Switching those sites to the two-rung
  `agent_key_from_pane(shadow_command, shadow_pane_pid)` — which this task
  supplies — is the root fix; adding detectors without it leaves the case broken.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-13T18:29:57Z status=pass attempt=1 type=human
