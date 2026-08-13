---
priority: medium
effort: medium
depends: [1509]
issue_type: feature
status: Ready
labels: [shadow, aitask_monitormini, codex, opencode]
gates: [risk_evaluated]
anchor: 1159
created_at: 2026-08-14 00:04
updated_at: 2026-08-14 00:04
---

Let a Codex- or OpenCode-**followed** pane arm the auto-recheck loop, closing the followed half of cross-agent loop support after t1509 closes the shadow half. Two changes: widen `REVIEW_LOOP_AGENTS` per agent behind live evidence, and add `NATIVE_DIALOG_BOUNDARIES` rows so work classification does not degrade to `UNKNOWN` whenever one of those agents sits at a native dialog.

## Why this is a separate task from t1467

t1467 wired Codex/OpenCode prompt markers, which made `workflow_phase.live_tiers_available` true for both. That predicate previously doubled as minimonitor's arming gate, so the loop would have unlocked for them **as a side effect of adding a marker**. It was deliberately split (t1467 decision 6):

- `live_tiers_available(agent)` — "can an advisory phase hint be derived?" — true for all three agents today.
- `review_loop_agent_supported(agent)` — "may a loop that **injects keystrokes** into the shadow pane be armed?" — `("claude",)`.

The second must be earned per agent with its own live evidence, not inherited. That is this task.

## What already exists — do NOT redo it

t1467 shipped the per-agent **question-block** boundaries, so `classify_followed_change`'s `SELECTION_ONLY` path already works for both agents' question widgets:

- `workflow_phase.QUESTION_BLOCK_BOUNDARIES["codex"]` — the `Question N/M (K unanswered)` header.
- `workflow_phase.QUESTION_BLOCK_STRATEGIES["opencode"]` — the contiguous `┃`-gutter scan (that widget has no header line).
- `QUESTION_WIDGET_KINDS` filled for both; `classify_followed_change` already threads the agent into `current_question_block`.

It also shipped the prompt patterns (`codex_question`, `codex_permission`, `opencode_question`, `opencode_permission`) and the two-rung identity resolver `agent_keys.agent_key_from_pane`. Reuse all of it.

## The actual gap

`classify_followed_change` (`.aitask-scripts/monitor/review_loop.py`) ends with a conservative fallthrough: a prompt kind with no boundary strategy returns `UNKNOWN`. `NATIVE_DIALOG_BOUNDARIES` holds exactly one row, `("claude", "claude_plan_approval")`. So for a Codex or OpenCode followed pane parked at `codex_permission` / `codex_yes_proceed` / `opencode_permission`, every content change classifies `UNKNOWN` — which never satisfies the work latch and never resets it.

That is **safe but under-detecting**: the loop simply would not observe work done while such a dialog is up. Fix it by adding boundary rows, never by loosening the `UNKNOWN` default — that default is the reason a kind with no strategy cannot misfire, and it must survive this task.

## Boundary candidates (measured in t1467 — confirm, do not trust)

Captured live through the monitor's own path (`capture-pane -p -e` + `strip_ansi`), Codex CLI 0.146.0 / OpenCode 1.18.18, 163x50 pane:

| agent | dialog | candidate boundary line | distance above bottom |
|---|---|---|---|
| codex | exec approval | `Would you like to run the following command?` | 13 |
| opencode | permission | `△ Permission required` | 10 |

Both appeared once and above the option rows, which is the shape a boundary needs. They were measured as *dialog headers*, though, not validated as *boundaries*: before shipping, confirm for each that it appears exactly once, only while the dialog is live, and always above the content that changes. Re-measure rather than copying these literals on faith — they are version-sensitive TUI text (the t1420/t1474/t1509 practice).

## Safety bar for widening `REVIEW_LOOP_AGENTS`

Arming does not change *what* is injected (the prompt still goes to the shadow pane), but a wrong work classification causes an extra recheck round. Require, per agent, before adding it to the tuple:

- a live session where the loop arms with that agent as the **followed** pane and fires exactly one automatic round;
- a live confirmation that pure option-cursor movement inside its question widget fires **nothing** (the `SELECTION_ONLY` path);
- the same for its native dialog once the boundary row exists.

Widen the tuple one agent at a time. An agent whose evidence is not in hand stays out, and the arm refusal must remain reachable and accurate for it.

## Key files

- `.aitask-scripts/monitor/review_loop.py` — `REVIEW_LOOP_AGENTS`, `review_loop_agent_supported`, `NATIVE_DIALOG_BOUNDARIES`, `classify_followed_change`.
- `.aitask-scripts/monitor/minimonitor_app.py` — `action_toggle_review_loop`'s followed-agent refusal ("the recheck loop is Claude-only for now"); its wording must track whatever this task ships.
- `tests/test_review_loop.py` — `ReviewLoopAgentSupportTests` and `PerAgentBlockBoundaryTests` (both added by t1467) are the cases to extend, not duplicate.
- `tests/test_minimonitor_concern_action.py` — `test_refuses_followed_agent_the_loop_does_not_support` pins the refusal; retarget it onto whatever remains unsupported rather than deleting it.

## Verification

- Per agent and per native dialog: `SELECTION_ONLY` for an in-dialog redraw, `WORK` for scrollback growth above the boundary — both directions, or the row proves nothing.
- **The conservative default survives:** a prompt kind with no boundary strategy still returns `UNKNOWN`. Assert it explicitly; it is the property that keeps an unmapped dialog from misfiring.
- `review_loop_agent_supported` truth table updated, and still False for an agent without evidence; the arm refusal still fires and names that agent.
- Live per agent: the three observations in the safety bar above.
- `bash tests/run_all_python_tests.sh` — read the final stderr verdict line only.

## Coordination

- **t1509** (shadow-readiness detectors for non-Claude shadows) — `depends:` on it deliberately. A loop needs BOTH ends: arming checks the followed agent *and* that the shadow agent has a readiness detector. Landing this half first would produce a pane that can arm but whose shadow is never ready — an armable loop that never fires, which is a worse failure than the current honest refusal. t1509 also owns switching the shadow-side identity resolution to the two-rung `agent_key_from_pane`, without which a Codex shadow (reporting `node`) never resolves at all.
- **t1467** (archived) — supplied the question-block boundaries, prompt patterns and identity resolver listed above. Its archived plan records the live captures and the measured geometry.
- **t1159_5** (aggregate manual verification of the loop) — its checklist assumes an armable loop; once both halves land, verify the cross-agent pairings there rather than duplicating the live runs.
