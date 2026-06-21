---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitask_monitormini, tmux, codeagent, claudeskills, gates]
children_to_implement: [t986_2, t986_7]
created_at: 2026-06-14 15:36
updated_at: 2026-06-15 19:02
boardidx: 200
---

## Goal

Add **shadow** (the "shadow agent"; code identifier `shadow`) — a minimonitor-triggered AI companion agent that captures the followed coding agent's tmux terminal output and helps the user reason about it. It both **explains** the output (and answers questions about it) and can **critically interrogate** a plan with challenge / probe / Socratic questions. The companion is a *second* coding-agent CLI (configurable agent+model) spawned, by default, in the **same tmux window** as the agent it shadows.

(Display name **shadow** / "shadow agent"; code identifier `shadow` for the codeagent operation key / pane-classification marker — avoiding the existing `explain` codeagent op / codebrowser file-history explainer.)

## Use cases

1. **Explain a plan / output that is too technical or buried.** Implementation plans produced in the task-workflow can be hard to follow because they're overly technical, or because the info the user cares about is buried deep. `shadow` reads the captured output and explains it in plain terms.
2. **Help answer an `AskUserQuestion` shown WITHOUT its source context.** Some workflow prompts appear in the terminal without the source task/plan visible (observed example: a session working `t635_3`). In this case `shadow` must **auto-fetch the most recent stored task file + plan file** for that task to give the user enough context to understand and answer. Advisory only — it explains/suggests; the user types the answer themselves (it does NOT inject keystrokes into the source agent).
3. **Challenge / probe / Socratic questioning of a plan.** Beyond explaining, `shadow` can act as a critical interlocutor: read the produced implementation plan (from the captured output and/or the fetched plan file) and generate **probing, adversarial, and Socratic questions** that pressure-test it — surfacing hidden assumptions, unaddressed edge cases, blast-radius/cleanliness concerns, and "what if someone edits this unaware?" risks. Purpose: help the user (or the source agent, via the user) find weaknesses before approving the plan. Still advisory-only; the questions are presented to the user, not injected into the source agent.

**Single mode, instruction-driven (NOT a mode selector).** Use cases 1–3 are *capabilities*, not separate launch modes. The shadow runs **one unified flow**; which capability applies is decided by the user's free-form request to the shadow agent once it is running. The skill workflow embeds the user's instruction and serves it (autodetecting phase + fetching context as needed). There is no explain-vs-challenge selector.

## Design decisions (confirmed with user during exploration)

- **Multi-agent-per-window: full refactor.** Do the proper refactor so a tmux window can robustly hold N real agents (key monitor state by `pane_id`, not `window_name`). **AND** the `shadow` pane must be classified as a *companion/helper* pane (like minimonitor itself) so it is **never listed among agents** in monitor/minimonitor.
- **Phase autodetection: ledger-first, text fallback.** Prefer the `t635` gate/checkpoint ledger to determine which workflow phase the source agent is in (planning / risk-eval / implementation review / AskUserQuestion / etc.); fall back to scraping terminal markers when the ledger lacks the phase.
- **Advisory-only role.** `shadow` is read-only w.r.t. the source agent. It never forwards answers/keystrokes back into the source pane.
- **Default placement:** same window (new pane) as the source agent; configurable to a separate window. Default agent+model and the same-window-vs-new-window choice are both configurable in settings.

### Design update (2026-06-14) — phase detection deprioritized

Re-examined during a `/aitask-pick` of t986_2. **Phase autodetection (t986_2) is
now considered NON-critical and has been postponed** (status: Postponed). The
shadow's core value is to **spawn fast, be immediately available, and answer ANY
question** the user asks about the followed agent — explain what it's doing,
explain plans, and optionally link sibling-task context. Those capabilities
(served by t986_3 context-fetch and the t986_4 skill) do **not** require knowing
the followed agent's workflow phase.

Implications for the remaining children:
- **t986_4 (shadow skill) must NOT be phase-gated.** Phase is, at most, advisory
  context for *possible future* features; it must never restrict which questions
  the user can ask, nor be a prerequisite for the shadow to start helping. Build
  t986_4 around "answer any free-form question + explain + fetch context", not
  around a phase router.
- **t986_2 stays Postponed** until a concrete feature needs the followed agent's
  phase. Its `depends:`/`children_to_implement` membership is unchanged; the
  t635_1 substrate is landed so reviving it is cheap.

### Design update (during t986_4) — skill is a user-invocable command

t986_4 landed the skill as a **user-invocable command** `/aitask-shadow`
(`user-invocable: true`), NOT the originally-planned `user-invocable: false`
skill. Reason: a spawned agent CLI can only be triggered non-headlessly by a
**slash command on argv** (the same mechanism as `/aitask-pick`); a
non-invocable skill is not discoverable as a slash command and can only be
read-and-followed by a parent skill in the same session, which a freshly-spawned
shadow does not have (and `claude -p` headless is ruled out). Shape: invocable +
static (single `SKILL.md` + sub-procedure `.md` files, no profile/`.j2`/stub),
modeled on `aitask-contribute`.

**Capture contract (t986_4 ↔ t986_5):** the launcher passes only
`/aitask-shadow <followed_pane_id> [<source_task_id>]`; the skill captures the
followed pane **on demand** via the new `aitask_shadow_capture.sh`
(escape-free stdout) so it always reads current output. The launcher does NOT
pre-capture content into the spawn (argv can't carry 100+ KB of screen text).

## Key findings / blast radius (from exploration)

**minimonitor is the host.** It already runs as a companion pane, captures the agent pane (`monitor_core.py:capture_pane()` → `tmux capture-pane -p -e`), maps window→task via `TaskInfoCache` (`_TASK_ID_RE = agent-(pick|qa)-(\d+...)`), and shows a `TaskDetailDialog` (`i`, with plan toggle `p`). The new work is the trigger/spawn glue + the skill + the substrate hardening.

**tmux layer is safe; app layer is not.** The tmux gateway (`lib/tmux_exec.py/.sh`) and capture are pane-keyed. Six app-layer sites in `monitor/monitor_core.py` + `monitor/minimonitor_app.py` assume one agent per window — these are the multi-agent blast radius:
1. Task-id from window name (`_TASK_ID_RE`, `TaskInfoCache` keyed by `window_name`).
2. Monitor UI display (task-id per window).
3. `kill_agent_pane_smart()` — kills the WHOLE window when no other non-companion panes remain.
4. minimonitor `_find_sibling_pane_id()` — returns `other_panes[0]` (assumes one agent pane).
5. Pane-`.0` refocus after companion spawn (`agent_launch_utils.py`).
6. `pane-died` companion-cleanup hook (`aitask_companion_cleanup.sh`) — assumes one primary per window.
Fix: key state by `pane_id`; extend companion classification (`_is_companion_process()` / `classify_pane`) to recognize the `shadow` pane.

**Config plumbing exists.** `codeagent_config.json` holds per-operation agent+model defaults (resolution chain in `lib/agent_string.sh` + `aitask_codeagent.sh`); `project_config.yaml` `tmux.*` + `settings/settings_app.py` (`PROJECT_CONFIG_SCHEMA`) is where the window-placement toggle goes. NOTE: the existing `defaults.explain` key is codebrowser's file-history explainer — use a new operation key (`shadow`), do not reuse `explain`.

**Skill shape.** User-invocable command (`user-invocable: true`) — see "Design update (during t986_4)" above for why a spawned shadow needs a slash-command surface. Invocable + static: single `SKILL.md` + sub-procedure `.md` files, no stub/`.j2` pair (modeled on `aitask-contribute`). Context fetch: `aitask_shadow_context.sh <task_id>` (wraps `aitask_query_files.sh`), `aitask_shadow_capture.sh <pane_id>` for the live screen, and `aitask_explain_context.sh` for historical plans. Per-agent (Codex/OpenCode) command-wrapper ports are follow-ups.

## Decomposition (finalized — see `aiplans/p986/` for per-child plans)

Approved split: **6 child tasks + 1 aggregate manual-verification sibling.**
Testability-first: pure headless units extracted with their own tests.
1. **t986_1 — Multi-agent-per-window substrate + shadow helper-pane exclusion** — re-key monitor state by `pane_id`; fix the 6 assumption sites; extend `_is_companion_process`/`classify_pane` so the `shadow` pane is excluded from agent lists; pure pane→task units + tests.
2. **t986_2 — Phase-autodetection module** — pure headless; ledger-first (imports `derive_status`/`parse_gate_runs` from `gate_ledger.py`; coordinates `t635_8`), terminal-text-marker fallback; fixtures + tests.
3. **t986_3 — Task/plan context-fetch utility** — given a source task id, fetch task file + most-recent plan + optional sibling context (wraps `aitask_query_files.sh` / `aitask_explain_context.sh`); tests.
4. **t986_4 — The `/aitask-shadow` user-invocable command** — `SKILL.md` dispatcher (single instruction-driven flow): capture the followed pane on demand (`aitask_shadow_capture.sh`), fetch context (#3), serve the user's free-form request (explain / answer / challenge) inline or via per-analysis sub-procedure files (`plan-explain`/`plan-challenge`/`plan-socratic`/`plan-assumptions`). Phase (#2) dropped — Postponed. Advisory-only; no mode selector.
5. **t986_5 — minimonitor trigger + spawn glue + settings/config** — keybinding/action on the followed agent; capture output; spawn the `shadow` agent (codeagent op + `agent_launch_utils`) in the same window by default; add `defaults.shadow` to `codeagent_config.json` + `project_config.yaml`/settings-TUI same-window-vs-new-window toggle.
6. **t986_6 — Docs** — aidocs (`tmux_gateway.md` multi-agent note, `tui_conventions.md` shadow-companion update, `monitor_idle_and_prompt_detection.md` if phase markers added) + website docs.
7. **t986_7 — Aggregate manual-verification sibling** (auto-created) — live flow: shadow launch in same window, explain/answer/challenge, multi-agent-window behavior, and shadow-pane-not-listed-among-agents.

## Coordination dependencies (not folds)

- **`t635_8` (python gate ledger parser)** + the `t635` gate-ledger family — phase autodetection (#3) is ledger-first and should consume the parser. Add a reverse coordination note on `t635_8` at planning time.
- **`t719` (monitor tmux-control-mode refactor)** — touches the same `monitor_core.py`; coordinate the multi-agent-per-window refactor (#1) to avoid conflicts.

## Cross-agent note

Per repo conventions, author the skill in the Claude Code source first; suggest follow-up tasks to port to Codex CLI / OpenCode if the change touches agent-specific surfaces.
