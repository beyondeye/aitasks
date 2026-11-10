---
priority: medium
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [sitrep, tui, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-10 22:36
updated_at: 2026-11-10 23:20
---

## Origin

Risk-mitigation ("before") for t2275, created at Step 7 from the approved plan's risk evaluation.

## Risk addressed

goal-achievement — composer grammar unmeasured at shadow pane widths

- The composer grammar (`composer_payload`) was measured at 120-column panes only. Shadow panes
  are about 60 columns (`shadow_pane_width`), so the ~110-char recheck prompt wraps there in every agent.
  If the W-relative width rules do not hold at 60, every recheck holds with
  `pre_enter_composer_unprovable` / `_changed`. That fails closed, with no wrong submit, but it breaks
  the auto-recheck loop · severity: medium · → mitigation: measure_shadow_width_composer

## Goal

t2275 (plan: `aiplans/p2275_shared_agent_submit_helper.md`) moves the minimonitor's shadow-recheck
Enter onto the same per-Enter composer-payload proof the sitrep delivery uses
(`review_loop.composer_payload` + `agent_request_delivery.payload_matches`, t2211_4). That proof's
per-agent grammar (region delimiters, continuation indent, content width, word-wrap rule, all
expressed as functions of the pane width W) was measured live only at **120x30** panes
(`tests/sitrep_request_fixtures.py`; the measurement table is in
`aiplans/archived/p2211/p2211_4_sitrep_tui_guarded_request_delivery.md`, section `## Measurement`).
Shadow panes are split at `shadow_pane_width` (default 60, `monitor_core` spawn), so the recheck
prompt from `review_loop.compose_recheck_prompt` wraps across rows there.

Measure it before t2275 relies on it:

1. On an isolated tmux server (`TMUX_TMPDIR=<scratch>`, `tmux -f /dev/null`, as in the t2211_4
   spike), run real claude, codex and opencode at **60 columns** and at one narrower width (e.g. 44).
2. For each agent and width, paste each of the three real recheck prompts
   (`compose_recheck_prompt` for phase PLAN, IMPLEMENT and None, with a round number) into the
   composer, and capture at production extent (`capture-pane -p -e -S -15`). Also capture an
   appended-text variant (prompt + " plus my own words") and a post-Enter capture.
3. Store the captures as fixtures in a new `tests/shadow_recheck_fixtures.py` (same tuple shape
   as `sitrep_request_fixtures.FIXTURES`: agent, pane_width, state, request, raw). Never trim
   them, and scrub any user-identifying text (session names, paths) the way t2211_4 dropped
   `codex_at_end`.
4. Add a test asserting `composer_payload(raw, agent, width)` + `payload_matches(..., prompt)`
   accept every genuine capture and reject every appended one.
5. If any agent's grammar fails at these widths, fix `review_loop.composer_payload` for that
   agent, re-pin it against both fixture sets (120 and the new widths), and record the corrected
   rule in this task's plan. If an agent cannot be measured (not installed), say so explicitly.
   t2275 must then treat that agent as unprovable rather than assume the 120-column rule.

Record the measurement table (agent x width: rows, content width, wrap rule observed, match
result) in this task's plan. t2275's step 5 renders the minimonitor test fake's composer from
these fixtures, so leave the fixture names stable and documented.
