---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: [2280]
issue_type: refactor
status: Ready
labels: [sitrep, tui, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [2280]
folded_tasks: [2274]
anchor: 2175
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-11-10 12:42
updated_at: 2026-11-10 22:37
---

## Origin

Risk-mitigation ("after") follow-up for t2211_4, created at Step 8d after implementation landed.

## Risk addressed

code-health — duplicated pre-Enter/mode-gate/retry loop in minimonitor and the sitrep delivery can drift

- Two implementations of the same pre-Enter / mode-gate / bounded-retry loop
  (`minimonitor_app._submit_shadow_prompt` and `deliver_sitrep_request`) can drift; a fix to
  one (e.g. a new t2001-style hazard) silently misses the other · severity: medium ·
  → mitigation: shared_agent_submit_helper

## Goal

Extract ONE shared submit helper and use it from both callers:
- `.aitask-scripts/monitor/minimonitor_app.py` `_submit_shadow_prompt` (L6011-6170, with
  `_fire_shadow_recheck` L5910-6009 writing the prompt);
- `.aitask-scripts/monitor/agent_request_delivery.py` `deliver_sitrep_request`, the
  phase-3 loop (committed in t2211_4, e16e440e4).

The helper owns the shared sequence: drain, the pre-Enter proof, the pane-mode read as
the last await before every Enter, the Enter, the post-Enter verification, and the bounded
retry with `SHADOW_SUBMIT_RETRIES`.

Keep each caller's result labels. The minimonitor returns `('sent' | 'not_ready' |
'failed', HOLD_*/DISARM_* code)` and checks its delivery token after every await; the
sitrep delivery returns `DeliveryResult` codes. Pin every caller's labels against
pre-refactor behaviour (the "dedupe keeps each caller's labels" rule).

Mind the difference between the two Enter transports. The minimonitor uses
`send_keys(..., "Enter")`, while the sitrep path uses the identity-guarded, acked
`guarded_send_key`. Decide whether the minimonitor should adopt the guarded dispatch too.

Coordinate with t2274 (minimonitor recheck Enter needs the composer payload proof).
t2211_4's per-Enter proof (`review_loop.composer_payload` + `payload_matches`) is what the
minimonitor lacks. Whichever task lands first should carry the proof into the shared
helper, and the other should consume it.

## Merged from t2274: minimonitor recheck enter needs composer payload proof


## Origin

Spawned from t2211_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/minimonitor_app.py:6011-6170` — `_submit_shadow_prompt`
  authorises each recheck Enter on `SHADOW_BUSY` alone. It never proves that the shadow
  composer holds exactly the recheck prompt, so text a user appended (or a draft typed
  after a submit that read BUSY) would be submitted. This is the same hazard class as the
  t2211_4 plan-review finding.

## Diagnostic context

t2211_4 built guarded request delivery from the sitrep TUI into the sitrep agent
(`.aitask-scripts/monitor/agent_request_delivery.py`, committed e16e440e4). Two
plan/implementation-review findings there apply equally to the minimonitor's
review-loop delivery into the SHADOW pane:

1. `shadow_state == SHADOW_BUSY` only says the composer holds SOME typed text. A search
   of the capture for "our" text cannot tell the composer from the transcript either.
   That design accepted (a) the request with user text appended, and (b) on a retry, the
   request echoed in history beside a foreign draft, so the retry Enter would submit the
   user's draft.
2. A BUSY read AFTER an Enter is a swallowed Enter only when the composer still holds
   exactly the text that was sent. Otherwise the text may already have been submitted,
   and reporting "not submitted" (or retrying) invites a duplicate.

The minimonitor path (`_fire_shadow_recheck` L5910-6009 writes the prompt with
`send_keys(..., literal=True)`; `_submit_shadow_prompt` L6011-6170 sends Enter):

- before each Enter it requires `before == SHADOW_BUSY` plus the t2001 mode gate, never
  that the BUSY composer holds exactly `prompt`;
- after an Enter, a BUSY read always `continue`s to a retry Enter, so a user typing into
  the shadow right after a real submit gets their draft submitted by the retry.

## Suggested fix

Reuse t2211_4's per-agent composer reader and matcher. Before every Enter (retries
included), require `payload_matches(review_loop.composer_payload(tail, agent, pane_width),
prompt)`. Treat a BUSY post-Enter read whose payload differs as "unverified" (hold or
warn), never as a swallowed Enter. The reader is
`review_loop.composer_payload` / `PAYLOAD_GRAMMAR_AGENTS`, and the matcher is
`agent_request_delivery.payload_matches`; both are measured and pinned by
`tests/sitrep_request_fixtures.py`. Mind that the recheck prompt is multi-word and may
wrap: `payload_matches` already handles justified wraps. Also check the prompt is single
spaced and one line (`agent_request_delivery.request_line_error`).

Coordinate with the `shared_agent_submit_helper` risk-mitigation follow-up of t2211_4,
which extracts one shared submit helper for both paths. Whichever lands first should
carry the payload proof, and the other should consume it instead of duplicating it.

Regression tests:
- a shadow composer holding the prompt plus appended user text gets no Enter;
- a BUSY post-Enter read showing a foreign draft gets no retry Enter;
- a pre-fix control showing the BUSY-only check accepting both.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t2274** (`t2274_minimonitor_recheck_enter_needs_composer_payload_proof.md`)

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2280** id=2026-11-12T10:39:32Z.4105fda47d39ad1de2fe79db from=t2280 from_verified=yes at=2026-11-12T10:39:32Z base=c3cc5f5805ac1b581db8b264a281e620b997ea56 base_branch=main dirty=yes host=omg16
>
> | t2280 (the "before" mitigation for your goal-achievement risk) landed in c3cc5f580. Advisory claims, all tree-relative to that commit:
> | 
> | 1. Fixtures: tests/shadow_recheck_fixtures.py — FIXTURES tuple shape (agent, pane_width, state, request, raw), same as sitrep_request_fixtures; names `<agent>_w<W>_<variant>` for W in WIDTHS=(60, 44); UNMEASURED = {} (all three agents measured). Variants: recheck_plan/recheck_impl/recheck_generic (= compose_recheck_prompt(PLAN|IMPLEMENT|None, 1)), appended, history_draft, post_enter, edge_*, hyphen_*, midtoken, endword_*/endhyphen_*. Pinned by tests/test_shadow_recheck_composer.py.
> | 
> | 2. The W-relative width rules hold at 60/44 (claude W-4, codex W-3, opencode border-5 with word wrap at content-1). BUT codex and opencode also break a line right AFTER a hyphen ("re-run the plan-" / "challenge"); claude never does. Before the fix the real PLAN/IMPLEMENT recheck prompt was unprovable for opencode at both shadow widths (your minimonitor would have held every such recheck). Fixed: ComposerPayload.hyphen_breaks (codex/opencode True) and payload_matches now justifies every break by the moved piece and an ending-based limit. Your fake composer for codex/opencode must hyphen-break the same way (see the hyphen_* and recheck_* fixtures) or genuine-composer cases will read as unprovable.
> | 
> | 3. Your plan step 1 moves payload_matches/display_width/_WORD_RE/_pane_width into agent_submit.py: the new private helpers `_FRAGMENT_RE`, `_moved_piece` and `_hyphen_justified` in agent_request_delivery.py are part of payload_matches now and must move with it (your one-shot AST check's moved-name list needs them too).
> | 
> | 4. Measured unprovable case: a codex composer whose last row fills exactly W-3 reads composer_payload None (codex moves its cursor onto an empty row, indistinguishable from a typed blank line). Deliberately kept fail-closed. A recheck whose last row happens to be W-3 at some width will hold as pre_enter_composer_unprovable; not hit at 60/44.
> | 
> | 5. tests/test_sitrep_request_delivery.py::test_opencode_wraps_one_column_short_of_a_hard_break was corrected (its synthetic final-word-at-content-width assertion contradicted live measurement), so "unchanged assertions must pass as-is" now means as of c3cc5f580.
> | 
> | Details: aiplans/archived/p2280_measure_shadow_width_composer.md, sections "Measurement" and "Post-Review Changes".

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-10T20:36:04Z status=pass attempt=1 type=human
