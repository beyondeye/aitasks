---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t1159_1]
issue_type: feature
status: Implementing
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/fable5
created_at: 2026-08-11 15:33
updated_at: 2026-08-12 17:44
---

Build the minimonitor-orchestrated auto-recheck loop: a pure state-machine module plus minimonitor wiring that, when armed, sends "refetch and recheck round N" into the SHADOW pane when the followed agent settles at a prompt after new output. The critical seam of t1159 (parent design: `aiplans/p1159_shadow_review_loop_automation.md`; child plan: `aiplans/p1159/p1159_2_auto_recheck_loop.md`). Depends on t1159_1 (round metadata: expected-round derivation and dedup lift).

## Context

Today the user manually watches the followed agent and types "refetch and recheck" into the shadow pane (there is NO mechanism at all — only free-text). The 2026-08-05 scope clarification makes this direction the critical, safe seam: it drives the shadow (the advisory companion), never the followed agent. The trigger inputs exist since t1420/t1474: `PaneSnapshot.awaiting_input` (prompt patterns) + `compute_shadow_staleness` (`@aitask_shadow_analyzed_at` vs `get_last_change_wall`) + the per-tick phase signal.

## Architecture (user-confirmed — do not reopen)

Minimonitor-orchestrated. New pure module `.aitask-scripts/monitor/review_loop.py` (no tmux/Textual/IO — testable like `concern_parser.py`):

- `ReviewLoopController`: states DISARMED/WAITING/FIRED; `tick(agent_present, shadow_present, awaiting_input, stale, shadow_ready, modal_open, now) -> 'none'|'fire'|'auto_disarm'`. EDGE-driven: a fired recheck makes the shadow re-capture, which restamps `@aitask_shadow_analyzed_at` and CLEARS the staleness that fired it — so after a fire stay FIRED until `stale is False` is positively observed, then re-arm. Debounce DEBOUNCE_TICKS=3 consecutive ticks of (`awaiting_input is True` AND `stale is True`); any negative/None resets the streak (t1446 AUTO_CLOSE "only positive evidence counts" pattern, minimonitor_app.py:666-701). Cooldown COOLDOWN_SECONDS=45 across episodes. `None` staleness never advances nor clears (tri-state discipline).
- `shadow_prompt_ready(text) -> bool | None` — POSITIVE readiness, not inactivity. ALL THREE required: (a) positive: tail shows the shadow agent's EMPTY input composer (no typed text; pattern pinned from real-widget fixtures); (b) negative: no dialog/prompt pattern for that agent matches the tail (a dialog is a different interaction — Enter there answers it); (c) capture hash unchanged ≥2 consecutive ticks. Unknown/failed capture ⇒ not-ready. Hash stability alone is NEVER sufficient (passes a shadow parked at AskUserQuestion / tool approval / half-typed text). Version-sensitive patterns maintained in-place like `prompt_patterns.py` (t1474 practice).
- `SHADOW_READY_DETECTORS: dict[agent, detector]` — the shadow's agent is independently selectable (`E` → any configured codeagent), so a Claude followed pane can have a Codex/OpenCode shadow. Initially populated for `claude` only. Arm-time check covers BOTH sides: followed agent `live_tiers_available` (trigger) AND shadow agent in `SHADOW_READY_DETECTORS` (delivery) — visible refusal on either gap. Per-tick service re-resolves the shadow agent and auto-disarms visibly if swapped to an unsupported agent mid-loop.
- `compose_recheck_prompt(phase, expected_round) -> str`: total over ALL inputs (None/UNKNOWN/garbage → generic wording; PLAN → plan-challenge wording; IMPLEMENT/POSTIMPL → impl-challenge wording). `expected_round` = `parse_block_meta(prev shadow capture).round + 1` or None before any block; woven in as "recheck round <N>". Phase pre-selects WORDING only — it never gates firing (advisory-only contract; t1311/t1420 scar; `tests/test_shadow_phase_advisory.sh` has the pattern; a wrong/UNKNOWN phase must still fire — negative control required).

## Safety contract (reproduce in aidocs/framework/shadow_agent.md)

(1) The followed pane is NEVER written — `_fire_shadow_recheck` receives no followed pane id; a unit test asserts no send_keys call names it. (2) Opt-in + permanently visible banner. (3) Edge-driven once per episode + cooldown. (4) Positive-evidence debounce. (5) Never inject into a busy shadow — fire requires `shadow_ready is True` = the three-part positive readiness check (empty-composer AND no-dialog-pattern AND hash-stability; hash alone never sufficient); holds (streak preserved) otherwise. (6) Auto-disarm on shadow/agent disappearance (visible); pause (streak reset, no disarm) while a modal is open. (7) Single-line literal injection only (no bracketed paste). (8) Phase never gates firing.

## Key files to modify

- NEW `.aitask-scripts/monitor/review_loop.py` (controller + readiness + prompt composer; full code shape in the child plan).
- `.aitask-scripts/monitor/minimonitor_app.py`: `Binding("L", "toggle_review_loop", ...)` in BINDINGS (326-345; `L` is free); `action_toggle_review_loop` with per-action refusals (no agent / no shadow → suggest `e` / capability gaps on both sides); `_service_review_loop(snap, shadow_pane)` called from ALL THREE branches of `_maybe_offer_concerns` (2286-2369: agent-gone early return, shadow-gone early return, main path after `_restamp_shadow_phase` at 2323) using cached `_shadow_feedback_stale` — no new tmux traffic; `_fire_shadow_recheck` → `self._monitor.send_keys(shadow_pane, prompt, literal=True)` + `send_keys(shadow_pane, "Enter")` (monitor_core.py:2458-2472, `--` separator seam, tested by tests/test_monitor_tmux_injection.sh); banner `#mini-loop-status` copying the `_set_shadow_stale_banner` pattern (2137-2147, CSS 258-265, `_loop_banner_text` DOM-free test seam); key-hints Static (442-452) gains `L:auto-recheck loop`.
- `aidocs/framework/shadow_agent.md`: new "Review-loop automation" section (defer full docs sweep to t1159_4; this child adds at least the safety contract).

## Pre-phase (risk mitigation, inline — confirmed at parent planning)

**live_trigger_positive_control**: BEFORE wiring the loop, drive a real Claude pane through the monitor capture path and confirm live: `awaiting_input` asserts at an AskUserQuestion and at the plan-approval widget, and `_shadow_feedback_stale` flips True after a followed-pane change (t1475 never ran — these inputs are implementation-reported, not confirmed). In the same session capture the shadow-readiness fixtures: shadow-at-rest (empty composer) / streaming / at-dialog / with typed composer text — these pin `shadow_prompt_ready`.

## Verification

- NEW `tests/test_review_loop.py` (pure): full state-machine table (debounce exactly 3, resets on False/None, edge contract — no second fire while FIRED even with stale True forever, `stale is False` re-arms and None does not, cooldown, modal pause preserves-streak-resets semantics per plan, auto-disarm, DISARMED inert); shadow-busy hold (trigger satisfied + shadow_ready False/None → no fire, fires on first ready tick); `shadow_prompt_ready` against the captured fixtures; `compose_recheck_prompt` totality (every PHASES value + None + garbage, with/without expected_round → non-empty single line, no newline).
- `tests/test_minimonitor_concern_action.py` (extend, `_FakeMon` + `MiniMonitorApp.__new__` + spy fixtures): arm refusals both sides (followed without live tiers; claude followed + codex shadow → visible refusal, controller DISARMED); mid-loop shadow swap → auto-disarm; fire path: exactly two sends, both to the SHADOW pane id, first literal prompt then Enter, followed pane id in NO send call; recheck text carries round from previous block meta; banner seam transitions; ADVISORY NEGATIVE CONTROL: force a wrong phase and UNKNOWN through the fire path — fires in every case, nothing refused.
- Live injection smoke: extend `tests/test_minimonitor_concern_smoke.py` or sibling shell test modeled on `tests/test_monitor_tmux_injection.sh` — a real tmux pane receives the recheck line verbatim.
- `bash tests/run_all_python_tests.sh` — final stderr verdict line only.

## Coordination — t1493 (added 2026-08-12, from live evidence)

**The injected recheck may produce no block at all, which livelocks this loop.**
Verified live (session `thinking_back`, window `agent-pick-45_9`, shadow pane
`%183`, Codex shadow of a Claude pane): after the first plan-challenge round,
three successive free-text `refetch and recheck` rounds each re-entered the skill
(resolve-profile → render → `aitask_shadow_capture.sh`) and answered in **prose
only** — no fences, no items — including one round that raised a real new
concern. Cause: `SKILL.md.j2` Step 3 (lines 212-284) routes on the user's ask and
has **no entry for a re-review / recheck ask**, so the recheck reads as a
conversational follow-up rather than a fresh sub-procedure run.

Consequences for this child:

- `expected_round = parse_block_meta(prev capture).round + 1` never advances,
  because no new block ever arrives.
- The picker keeps re-presenting the FIRST round's concerns, and — since every
  capture restamps `@aitask_shadow_analyzed_at` — the staleness banner reports
  them as current. The loop then fires round after round with no visible change.
- t1159_1's metadata-only clean-round block does not cover this: it addresses the
  *clean* round, while this is a non-clean round that emits nothing.

**t1493** (`shadow_recheck_rounds_leave_stale_concerns_in_picker`, bug/high,
anchor 1159, `depends: [t1159_1]`) owns the fix: a routing entry for re-review
asks plus a per-round "always re-emit the block" producer rule, and a
consumer-side block-age freshness check. Its producer half should land **before,
or together with,** this child — otherwise the loop's happy path is unreachable.
Align `compose_recheck_prompt`'s wording with whatever routing trigger t1493
adds, so the injected line hits the new route deterministically.

Also from the same live session, relevant to the arm-time capability check here:
the shadow was **Codex** (`gpt-5.6-terra`) while `SHADOW_READY_DETECTORS` ships
`claude`-only — that real-world configuration refuses to arm. Worth confirming
the refusal message names the shadow's agent, since this is not a corner case.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-12T14:44:46Z status=pass attempt=1 type=human
